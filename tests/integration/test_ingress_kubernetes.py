# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the ingress relation on a Kubernetes substrate.

These tests verify the Kubernetes-specific code path of the ingress-configurator
charm: when the charm runs on a K8s substrate and receives ingress relation data,
it must create a NodePort service and forward node IPs + the NodePort as backend
addresses to haproxy via a cross-model haproxy-route relation.

Prerequisites (passed as pytest CLI options):
  --k8s-controller   Name of the Juju K8s controller (default: kubernetes)
  --machine-controller  Name of the Juju machine controller (default: localhost)
  --charm-file       Path to the packed ingress-configurator charm

Deployment topology:
  K8s model   : ingress-configurator  <──ingress──  any-charm (ingress requirer)
                      │
                haproxy-route (cross-model CMR)
                      │
  Machine model: haproxy  ◄──  self-signed-certificates
"""

import re
from typing import Callable

import jubilant
import pytest
from lightkube import Client
from lightkube.resources.core_v1 import Node
from requests import Session

from .conftest import (
    CERTIFICATES_APP_NAME,
    HAPROXY_APP_NAME,
    JUJU_WAIT_TIMEOUT,
    MOCK_HAPROXY_HOSTNAME,
    get_unit_addresses,
)


@pytest.mark.abort_on_fail
def test_kubernetes_ingress_routes_through_haproxy(
    haproxy: str,
    k8s_ingress_requirer: str,
    http_session: Callable[..., Session],
    lxd_controller: str,
    lxd_model: str,
) -> None:
    """Deploy ingress-configurator and AnyCharm on K8s, integrate with machine haproxy.

    arrange: ingress-configurator and any-charm (ingress requirer) are deployed on a
        Kubernetes Juju model; haproxy and self-signed-certificates are deployed on
        a separate machine Juju model; the haproxy-route endpoint is offered cross-model.
    act: integrate the ingress requirer with ingress-configurator, which triggers the K8s
        code path: a NodePort service is created, node IPs are fetched, and haproxy-route
        data is populated with those values.
    assert: all applications reach active status; the NodePort service for the ingress
        requirer exists in the Kubernetes cluster; haproxy backend addresses match the
        Kubernetes node IPs; haproxy routes HTTPS requests to the backend through the
        NodePort.
    """
    juju = jubilant.Juju(model=f"{lxd_controller}:{lxd_model}")
    juju.wait_timeout = JUJU_WAIT_TIMEOUT
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, CERTIFICATES_APP_NAME),
        error=jubilant.any_error,
    )
    haproxy_backend_ips = _get_haproxy_backend_server_ips(
        machine_model=juju,
        service_name=f"{k8s_ingress_requirer}-service",
    )
    haproxy_address = str(get_unit_addresses(juju, haproxy)[0])

    node_ips = _get_k8s_node_internal_ips()

    assert set(node_ips) == set(haproxy_backend_ips), (
        f"Haproxy backend IPs {sorted(haproxy_backend_ips)!r} "
        f"don't match K8s node IPs {sorted(node_ips)!r}"
    )

    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, haproxy_address)])
    response = session.get(f"https://{MOCK_HAPROXY_HOSTNAME}/", verify=False, timeout=30)
    assert response.status_code == 200
    assert "Apache2 Default Page" in response.text


def _get_k8s_node_internal_ips() -> list[str]:
    """Fetch InternalIP addresses of worker K8s nodes via lightkube.

    Uses the ambient ``KUBECONFIG`` (or in-cluster config) to create a
    lightkube :class:`~lightkube.Client` and lists all :class:`Node` resources,
    mirroring the logic in :func:`kubernetes.get_nodes_ips`.

    Returns:
        A list of InternalIP address strings for every worker node in the cluster.
    """
    client = Client()
    return [
        address.address
        for node in client.list(Node)
        if node.status
        and node.status.addresses
        and node.metadata
        and "node-role.kubernetes.io/worker" in set(node.metadata.labels or {})
        for address in node.status.addresses
        if address.type == "InternalIP"
    ]


def _get_haproxy_backend_server_ips(machine_model: jubilant.Juju, service_name: str) -> list[str]:
    """Read the haproxy config and return server IPs for the named backend.

    Reads ``/etc/haproxy/haproxy.cfg`` from the first haproxy unit and
    extracts the IP address of every ``server`` line in the ``backend
    <service_name>`` section.

    Args:
        machine_model: jubilant.Juju instance connected to the machine model.
        service_name: The haproxy backend name to look up (e.g.
            ``"ingress-requirer-service"``).

    Returns:
        A list of IP address strings found in the backend section's server lines.
    """
    unit = next(iter(machine_model.status().apps[HAPROXY_APP_NAME].units))
    task = machine_model.exec("cat /etc/haproxy/haproxy.cfg", unit=unit, log=False)
    config = task.stdout

    backend_match = re.search(
        rf"^backend {re.escape(service_name)}\b(.*?)(?=^[a-z]|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    )
    if not backend_match:
        return []
    backend_section = backend_match.group(1)
    return re.findall(r"^\s+server\s+\S+\s+(\d[\d.]+):", backend_section, re.MULTILINE)
