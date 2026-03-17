# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the ingress relation on a Kubernetes substrate.

These tests verify the Kubernetes-specific code path of the ingress-configurator
charm: when the charm runs on a K8s substrate and receives ingress relation data,
it must create a NodePort service and forward node IPs + the NodePort as backend
addresses to haproxy via a cross-model haproxy-route relation.

Prerequisites (passed as pytest CLI options):
  --k8s-controller   Name of the Juju K8s controller (default: microk8s)
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
import subprocess
from typing import Callable

import jubilant
import pytest
from lightkube import Client
from lightkube.resources.core_v1 import Node
from requests import Session

from .conftest import (
    CERTIFICATES_APP_NAME,
    HAPROXY_APP_NAME,
    INGRESS_REQUIRER_APP_NAME,
    MOCK_HAPROXY_HOSTNAME,
    get_unit_addresses,
)


@pytest.mark.abort_on_fail
def test_kubernetes_ingress_routes_through_haproxy(
    k8s_juju: jubilant.Juju,
    k8s_application: str,
    machine_haproxy: tuple[jubilant.Juju, str, str],
    k8s_ingress_requirer: str,
    http_session: Callable[..., Session],
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
    machine_model, _, _ = machine_haproxy

    k8s_juju.wait(
        lambda status: jubilant.all_active(status, k8s_application, k8s_ingress_requirer),
        error=jubilant.any_error,
    )
    machine_model.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, CERTIFICATES_APP_NAME),
        error=jubilant.any_error,
    )

    _assert_nodeport_service_exists(k8s_juju=k8s_juju, app_name=INGRESS_REQUIRER_APP_NAME)

    node_ips = _get_k8s_node_external_ips()
    haproxy_backend_ips = _get_haproxy_backend_server_ips(
        machine_model=machine_model,
        service_name=f"{INGRESS_REQUIRER_APP_NAME}-service",
    )
    assert set(node_ips) == set(haproxy_backend_ips), (
        f"Haproxy backend IPs {sorted(haproxy_backend_ips)!r} "
        f"don't match K8s node IPs {sorted(node_ips)!r}"
    )

    haproxy_address = str(get_unit_addresses(machine_model, HAPROXY_APP_NAME)[0])
    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, haproxy_address)])
    response = session.get(f"https://{MOCK_HAPROXY_HOSTNAME}/", verify=False, timeout=30)
    assert response.status_code == 200


def _assert_nodeport_service_exists(k8s_juju: jubilant.Juju, app_name: str) -> None:
    """Assert that the NodePort service for *app_name* exists in the K8s cluster.

    The service name follows the ``{app_name}-service`` convention used by
    :func:`kubernetes.create_nodeport_service`.

    Args:
        k8s_juju: jubilant.Juju instance connected to the K8s model.
        app_name: The application name whose NodePort service is checked.

    Raises:
        AssertionError: When the NodePort service is not found.
    """
    service_name = f"{app_name}-service"
    namespace = k8s_juju.model or "default"
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "service",
            service_name,
            "--namespace",
            namespace,
            "--output",
            "jsonpath={.spec.type}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"NodePort service '{service_name}' not found in namespace '{namespace}': {result.stderr}"
    )
    assert result.stdout == "NodePort", (
        f"Service '{service_name}' exists but has type '{result.stdout}', expected 'NodePort'"
    )


def _get_k8s_node_external_ips() -> list[str]:
    """Fetch ExternalIP addresses of all K8s nodes via lightkube.

    Uses the ambient ``KUBECONFIG`` (or in-cluster config) to create a
    lightkube :class:`~lightkube.Client` and lists all :class:`Node` resources,
    mirroring the logic in :func:`kubernetes.get_node_ips`.

    Returns:
        A list of ExternalIP address strings for every node in the cluster.
    """
    client = Client()
    return [
        address.address
        for node in client.list(Node)
        if node.status and node.status.addresses
        for address in node.status.addresses
        if address.type == "ExternalIP"
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
    task = machine_model.exec("cat /etc/haproxy/haproxy.cfg", unit=unit)
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
