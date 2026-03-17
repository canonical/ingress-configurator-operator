# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Kubernetes helper methods for interacting with the cluster via lightkube."""

import logging
from dataclasses import dataclass
from typing import Literal

from lightkube import ApiError, Client
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Node, Service

logger = logging.getLogger(__name__)

Protocol = Literal["TCP", "UDP", "SCTP"]


@dataclass(frozen=True)
class KubernetesData:
    """Value object holding Kubernetes API data needed for backend configuration.

    Populated from the results of :func:`get_node_ips` and
    :func:`get_kubernetes_data`.

    Attributes:
        node_ips: InternalIP addresses of all cluster nodes.
        service_name: The name of the NodePort service that was queried.
        service_target_port: The targetPort from the NodePort service.
        service_protocol: The transport protocol from the NodePort service.
    """

    node_ips: list[str]
    service_name: str
    service_target_port: int
    service_protocol: Protocol


def get_node_ips(client: Client) -> list[str]:
    """Fetch the InternalIP addresses of all nodes in the cluster.

    Args:
        client: A lightkube Client instance.

    Returns:
        A list of InternalIP addresses from all cluster nodes.
    """
    ips: list[str] = []
    for node in client.list(Node):
        if node.status and node.status.addresses:
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    ips.append(address.address)
    return ips


def create_nodeport_service(
    client: Client, port: int, protocol: Protocol, app_name: str
) -> Service:
    """Create a NodePort service for the given app.

    The service name is derived by suffixing the app name with "-service".

    Args:
        client: A lightkube Client instance.
        port: The port number to expose.
        protocol: The network protocol ("TCP", "UDP", or "SCTP").
        app_name: The app name used as the selector label and as the base for
            the service name.

    Returns:
        The created Kubernetes Service resource.
    """
    service = Service(
        metadata=ObjectMeta(name=f"{app_name}-service"),
        spec=ServiceSpec(
            type="NodePort",
            selector={"app": app_name},
            ports=[ServicePort(port=port, protocol=protocol)],
        ),
    )
    return client.create(service)


def replace_nodeport_service(
    client: Client, port: int, protocol: Protocol, app_name: str
) -> Service:
    """Replace the NodePort service for the given app with updated port and protocol.

    The service name is derived by suffixing the app name with "-service", matching
    the naming convention used by :func:`create_nodeport_service`.

    Args:
        client: A lightkube Client instance.
        port: The new port number to expose.
        protocol: The new network protocol ("TCP", "UDP", or "SCTP").
        app_name: The app name used as the selector label and as the base for
            the service name.

    Returns:
        The replaced Kubernetes Service resource.
    """
    service = Service(
        metadata=ObjectMeta(name=f"{app_name}-service"),
        spec=ServiceSpec(
            type="NodePort",
            selector={"app": app_name},
            ports=[ServicePort(port=port, protocol=protocol)],
        ),
    )
    return client.replace(service)


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
    the naming convention used by :func:`create_nodeport_service`.

    Args:
        client: A lightkube Client instance.
        app_name: The app name; the service is deleted as "{app_name}-service".
    """
    client.delete(Service, name=f"{app_name}-service")


def ensure_nodeport_service(
    client: Client, port: int, protocol: Protocol, app_name: str
) -> None:
    """Create or update the NodePort service so its port and protocol match the given values.

    If the service does not exist it is created. If it exists but its port or
    protocol differ from the supplied values it is replaced.

    Args:
        client: A lightkube Client instance.
        port: The desired port number.
        protocol: The desired network protocol ("TCP", "UDP", or "SCTP").
        app_name: The app name; the service is managed as "{app_name}-service".
    """
    try:
        service = get_nodeport_service(client, app_name)
        existing_port = service.spec.ports[0]
        if existing_port.port != port or existing_port.protocol != protocol:
            replace_nodeport_service(client, port, protocol, app_name)
    except ApiError as e:
        if e.status.code == 404:
            create_nodeport_service(client, port, protocol, app_name)
        else:
            raise


def get_kubernetes_data(client: Client, app_name: str) -> KubernetesData:
    """Fetch node IPs and NodePort service details and return structured data.

    Args:
        client: A lightkube Client instance.
        app_name: The app name; the service is looked up as "{app_name}-service".

    Returns:
        A KubernetesData instance populated with node IPs and service details.
    """
    node_ips = get_node_ips(client)
    service = get_nodeport_service(client, app_name)
    port = service.spec.ports[0]
    return KubernetesData(
        node_ips=node_ips,
        service_name=service.metadata.name,
        service_target_port=port.targetPort,
        service_protocol=port.protocol,
    )
