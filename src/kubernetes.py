# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Kubernetes helper methods for interacting with the cluster via lightkube."""

import logging
from typing import cast

from lightkube import ApiError, Client
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Node, Service

from state.charm_state import InvalidStateError, NodePortState

logger = logging.getLogger(__name__)


def get_nodes_ips(client: Client) -> list[str]:
    """Fetch the InternalIP addresses of nodes in the cluster.

    Args:
        client: A lightkube Client instance.

    Returns:
        A list of InternalIP addresses from all nodes.
    """
    nodes = client.list(Node)
    return [
        address.address
        for node in nodes
        if node.status and node.status.addresses
        for address in node.status.addresses
        if address and address.type == "InternalIP"
    ]


def ensure_nodeport_service(
    client: Client, port: int, service_name: str, remote_app_name: str, charm_name: str
) -> Service:
    """Create or update the NodePort service for the given app via server-side apply.

    An ``owning-charm`` annotation is set to ``charm_name`` so the service can
    be identified for cleanup later.

    Args:
        client: A lightkube Client instance.
        port: The port number to expose.
        service_name: The name of the Kubernetes service to create.
        remote_app_name: The name of the remote application to select.
        charm_name: The name of the owning charm, stored as an annotation.

    Returns:
        The applied Kubernetes Service resource.
    """
    service = Service(
        metadata=ObjectMeta(
            name=service_name,
            annotations={"owning-charm": charm_name},
        ),
        spec=ServiceSpec(
            type="NodePort",
            selector={"app.kubernetes.io/name": remote_app_name},
            ports=[ServicePort(port=port)],
        ),
    )
    try:
        return client.apply(service)
    except ApiError as e:
        if e.status.code == 403:
            raise InvalidStateError("This charm needs --trust to run on k8s substrates") from e
        raise


def delete_nodeport_services_owned_by(client: Client, charm_name: str) -> None:
    """Delete all NodePort services annotated as owned by the given charm.

    Identifies services by the ``owning-charm`` annotation matching
    ``charm_name`` and deletes each one.

    Args:
        client: A lightkube Client instance.
        charm_name: The owning charm name to match.
    """
    for service in client.list(Service):
        if (
            service.metadata
            and service.metadata.name
            and service.metadata.annotations
            and service.metadata.annotations.get("owning-charm") == charm_name
        ):
            client.delete(Service, name=service.metadata.name)


def get_nodeport_service(client: Client, service_name: str) -> Service:
    """Fetch the NodePort service by name.

    Args:
        client: A lightkube Client instance.
        service_name: The name of the Kubernetes service to fetch.

    Returns:
        The Kubernetes Service resource.
    """
    return client.get(Service, name=service_name)


def get_kubernetes_data(client: Client, service_name: str) -> NodePortState:
    """Fetch node IPs and NodePort service details and return structured data.

    Args:
        client: A lightkube Client instance.
        service_name: The name of the Kubernetes service to look up.

    Returns:
        A NodePortState instance populated with node IPs and service details.
    """
    node_ips = get_nodes_ips(client)
    service = get_nodeport_service(client, service_name)
    if service.spec is None or service.spec.ports is None:
        raise ValueError(f"NodePort service {service_name!r} has no spec or ports")
    if service.metadata is None or service.metadata.name is None:
        raise ValueError(f"NodePort service {service_name!r} has no metadata name")
    port = service.spec.ports[0]
    return NodePortState(
        backend_addresses=node_ips,
        service_name=service.metadata.name,
        backend_port=cast(int, port.nodePort),
    )
