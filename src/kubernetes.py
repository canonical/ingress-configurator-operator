# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Kubernetes helper methods for interacting with the cluster via lightkube."""

import logging
from typing import Literal, cast

from lightkube import ApiError, Client
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Node, Service

from state.charm_state import InvalidStateError, NodePortState

logger = logging.getLogger(__name__)

Protocol = Literal["TCP", "UDP", "SCTP"]


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
    client: Client, port: int, protocol: Protocol, app_name: str, charm_name: str
) -> Service:
    """Create or update the NodePort service for the given app via server-side apply.

    The service name is derived by suffixing the app name with "-service".
    An ``owning-charm`` annotation is set to ``charm_name`` so the service can
    be identified for cleanup later.

    Args:
        client: A lightkube Client instance.
        port: The port number to expose.
        protocol: The network protocol ("TCP", "UDP", or "SCTP").
        app_name: The app name used as the selector label and as the base for
            the service name.
        charm_name: The name of the owning charm, stored as an annotation.

    Returns:
        The applied Kubernetes Service resource.
    """
    service = Service(
        metadata=ObjectMeta(
            name=f"{app_name}-service",
            annotations={"owning-charm": charm_name},
        ),
        spec=ServiceSpec(
            type="NodePort",
            selector={"app": app_name},
            ports=[ServicePort(port=port, protocol=protocol)],
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


def get_nodeport_service(client: Client, app_name: str) -> Service:
    """Fetch the NodePort service for the given app.

    The service name is derived by suffixing app_name with "-service".

    Args:
        client: A lightkube Client instance.
        app_name: The app name; the service is looked up as "{app_name}-service".

    Returns:
        The Kubernetes Service resource.
    """
    return client.get(Service, name=f"{app_name}-service")


def delete_nodeport_service(client: Client, app_name: str) -> None:
    """Delete the NodePort service for the given app.

    The service name is derived by suffixing app_name with "-service", matching
    the naming convention used by :func:`ensure_nodeport_service`.

    Args:
        client: A lightkube Client instance.
        app_name: The app name; the service is deleted as "{app_name}-service".
    """
    client.delete(Service, name=f"{app_name}-service")


def get_kubernetes_data(client: Client, app_name: str) -> NodePortState:
    """Fetch node IPs and NodePort service details and return structured data.

    Args:
        client: A lightkube Client instance.
        app_name: The app name; the service is looked up as "{app_name}-service".

    Returns:
        A NodePortState instance populated with node IPs and service details.
    """
    node_ips = get_nodes_ips(client)
    service = get_nodeport_service(client, app_name)
    if service.spec is None or service.spec.ports is None:
        raise ValueError(f"NodePort service for {app_name!r} has no spec or ports")
    if service.metadata is None or service.metadata.name is None:
        raise ValueError(f"NodePort service for {app_name!r} has no metadata name")
    port = service.spec.ports[0]
    return NodePortState(
        backend_addresses=node_ips,
        service_name=service.metadata.name,
        backend_port=cast(int, port.nodePort),
        backend_protocol=cast(Protocol, port.protocol),
    )
