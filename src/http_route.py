# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""HTTPRoute resource management for gateway-route mode."""

import dataclasses
import logging

from lightkube import ApiError, Client
from lightkube.generic_resource import create_namespaced_resource
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Service
from lightkube.resources.discovery_v1 import EndpointSlice

from helpers import truncate_k8s_resource_name
from kubernetes import InvalidKubernetesPermissionError

logger = logging.getLogger(__name__)

CUSTOM_RESOURCE_GROUP_NAME = "gateway.networking.k8s.io"
HTTP_ROUTE_RESOURCE_NAME = "HTTPRoute"
HTTP_ROUTE_PLURAL = "httproutes"
MANAGED_BY_LABEL = "ingress-configurator.charm.juju.is/managed-by"


HTTPRouteResource = create_namespaced_resource(
    CUSTOM_RESOURCE_GROUP_NAME, "v1", HTTP_ROUTE_RESOURCE_NAME, HTTP_ROUTE_PLURAL
)


def http_listener_name(gateway_name: str, hostname: str) -> str:
    """Build the per-hostname HTTP listener name / sectionName.

    The name follows the convention ``{gateway_name}-http-{sanitized_hostname}``
    where dots in the hostname are replaced with hyphens. This mirrors the
    gateway-api-integrator's HTTP listener naming so HTTPRoutes reference the
    correct per-hostname listener.

    Args:
        gateway_name: The name of the Gateway K8s resource.
        hostname: The hostname for this listener.

    Returns:
        The listener name.
    """
    return f"{gateway_name}-http-{hostname.replace('.', '-')}"


def https_listener_name(gateway_name: str, hostname: str) -> str:
    """Build the per-hostname HTTPS listener name / sectionName.

    The name follows the convention ``{gateway_name}-https-{sanitized_hostname}``
    where dots in the hostname are replaced with hyphens.

    Args:
        gateway_name: The name of the Gateway K8s resource.
        hostname: The hostname for this listener.

    Returns:
        The listener name.
    """
    return f"{gateway_name}-https-{hostname.replace('.', '-')}"


def ensure_workload_backend_service(
    client: Client,
    namespace: str,
    name: str,
    target_app_name: str,
    port: int,
    owner_app_name: str,
) -> None:
    """Create or update a selector-based Service routing to pods of ``target_app_name``.

    Unlike the headless backend, this Service uses a pod selector rather than
    explicit Endpoints, so it works even when the target application has not
    opened its port in Juju.

    Args:
        client: The lightkube Client instance.
        namespace: The Kubernetes namespace to create the Service in.
        name: Name for the Service.
        target_app_name: Pod label value for ``app.kubernetes.io/name`` on the
            target application's pods.
        port: The port to expose and target.
        owner_app_name: Owning charm name, used as the value of the
            :data:`MANAGED_BY_LABEL` label.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    service = Service(
        metadata=ObjectMeta(
            name=name,
            namespace=namespace,
            labels={MANAGED_BY_LABEL: owner_app_name},
        ),
        spec=ServiceSpec(
            selector={"app.kubernetes.io/name": target_app_name},
            ports=[ServicePort(port=port, targetPort=port)],
        ),
    )
    try:
        client.apply(service, field_manager=owner_app_name, force=True)
    except ApiError as e:
        if e.status.code == 403:
            raise InvalidKubernetesPermissionError(
                "This charm needs --trust to run on k8s substrates"
            ) from e
        raise


def delete_backend_services_owned_by(
    client: Client,
    namespace: str,
    app_name: str,
    exclude: set[str] | None = None,
) -> None:
    """Delete all backend EndpointSlices and Services owned by ``app_name``.

    Resources are identified by a :data:`MANAGED_BY_LABEL` label matching ``app_name``.

    Args:
        client: The lightkube Client instance.
        namespace: The Kubernetes namespace to search in.
        app_name: The owning charm name to match.
        exclude: Optional set of resource names to skip deletion.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    exclude_set = exclude or set()
    try:
        for es in client.list(
            EndpointSlice, namespace=namespace, labels={MANAGED_BY_LABEL: app_name}
        ):
            if es.metadata and es.metadata.name and es.metadata.name not in exclude_set:
                client.delete(EndpointSlice, name=es.metadata.name, namespace=namespace)
        for service in client.list(
            Service, namespace=namespace, labels={MANAGED_BY_LABEL: app_name}
        ):
            if (
                service.metadata
                and service.metadata.name
                and service.metadata.name not in exclude_set
            ):
                client.delete(Service, name=service.metadata.name, namespace=namespace)
    except ApiError as e:
        if e.status.code == 403:
            raise InvalidKubernetesPermissionError(
                "This charm needs --trust to run on k8s substrates"
            ) from e
        raise


@dataclasses.dataclass
class HTTPRouteConfig:
    """Configuration for an HTTPRoute resource.

    Attributes:
        app_name: The name of the application.
        scheme: The scheme of the HTTPRoute ("http" or "https").
        gateway_name: parentRef gateway name.
        gateway_namespace: parentRef namespace.
        listener_names: List of sectionNames this route attaches to (e.g.
            per-hostname HTTP listener names, or a single HTTPS listener name).
        hostnames: List of hostnames for the HTTPRoute.
        paths: List of path prefixes.
        backend_service_name: The workload K8s Service name.
        backend_service_port: The workload port.
        redirect_https: If True, this route issues a 301 HTTPS redirect.
    """

    app_name: str
    scheme: str
    gateway_name: str
    gateway_namespace: str
    listener_names: list[str]
    hostnames: list[str]
    paths: list[str]
    backend_service_name: str
    backend_service_port: int
    redirect_https: bool = False


class HTTPRouteManager:
    """Manages HTTPRoute K8s resources for a fixed namespace and label set.

    Attributes:
        client: The lightkube client.
        namespace: The K8s namespace to manage resources in.
        labels: Labels applied to every managed resource (and used as selector).
    """

    def __init__(self, client: Client, namespace: str, labels: dict) -> None:
        """Initialise the manager.

        Args:
            client: The lightkube client.
            namespace: The K8s namespace to manage resources in.
            labels: Labels applied to every managed resource (and used as selector).
        """
        self.client = client
        self.namespace = namespace
        self.labels = labels

    @staticmethod
    def _build_spec(config: HTTPRouteConfig) -> dict[str, object]:
        """Build the HTTPRoute spec dict from a config.

        Args:
            config: The HTTPRoute configuration.

        Returns:
            A dict representing the HTTPRoute spec.
        """
        parent_refs: list[dict[str, str]] = [
            {
                "name": config.gateway_name,
                "namespace": config.gateway_namespace,
                "sectionName": listener_name,
            }
            for listener_name in config.listener_names
        ]

        if config.redirect_https:
            rules: list[dict[str, object]] = [
                {
                    "filters": [
                        {
                            "type": "RequestRedirect",
                            "requestRedirect": {
                                "scheme": "https",
                                "statusCode": 301,
                            },
                        }
                    ]
                }
            ]
        else:
            rules = [
                {
                    "matches": [
                        {"path": {"type": "PathPrefix", "value": path}} for path in config.paths
                    ],
                    "backendRefs": [
                        {
                            "name": config.backend_service_name,
                            "port": config.backend_service_port,
                        }
                    ],
                }
            ]

        spec: dict = {
            "parentRefs": parent_refs,
            "rules": rules,
        }
        if config.hostnames:
            spec["hostnames"] = config.hostnames

        return spec

    def apply(self, config: HTTPRouteConfig) -> str:
        """Create or patch (server-side apply) an HTTPRoute resource.

        Args:
            config: The HTTPRoute configuration.

        Raises:
            InvalidKubernetesPermissionError: When the charm lacks RBAC permissions (403).

        Returns:
            The resource name.
        """
        spec = self._build_spec(config)
        resource_name = truncate_k8s_resource_name(
            f"{config.app_name}-{config.backend_service_name}-{config.scheme}"
        )
        resource = HTTPRouteResource(
            metadata=ObjectMeta(
                name=resource_name,
                namespace=self.namespace,
                labels=self.labels,
            ),
            spec=spec,
        )
        try:
            self.client.apply(resource, field_manager=config.app_name, force=True)
        except ApiError as e:
            if e.status.code == 403:
                raise InvalidKubernetesPermissionError(
                    "This charm needs `juju trust` to manage HTTPRoute resources"
                ) from e
            raise
        logger.info("Applied HTTPRoute %s", resource_name)
        return resource_name

    def delete_stale(self, exclude: list[str] | None = None) -> None:
        """Delete all managed HTTPRoute resources except those in exclude.

        Args:
            exclude: Resource names to keep.
        """
        exclude_set = set(exclude or [])
        try:
            for route in self.client.list(
                HTTPRouteResource, namespace=self.namespace, labels=self.labels
            ):
                name = route.metadata.name  # type: ignore[union-attr]
                if not name:
                    raise ValueError("Encountered HTTPRoute resource with no name")
                if name not in exclude_set:
                    self.client.delete(HTTPRouteResource, name=name, namespace=self.namespace)
                    logger.info("Deleted stale HTTPRoute %s", name)
        except ApiError as e:
            if e.status.code == 403:
                raise InvalidKubernetesPermissionError(
                    "This charm needs `juju trust` to manage HTTPRoute resources"
                ) from e
            raise


def create_http_routes(
    http_route_manager: HTTPRouteManager,
    app_name: str,
    gateway_name: str,
    gateway_model: str,
    https_mode: str,
    hostnames: list[str],
    paths: list[str],
    backend_service_name: str,
    backend_service_port: int,
) -> None:
    """Create HTTPRoute K8s resources based on https_mode.

    Args:
        http_route_manager: The HTTPRouteManager to apply and clean up resources.
        app_name: Charm application name used in managed HTTPRoute resource names.
        gateway_name: Name of the Gateway K8s resource.
        gateway_model: Name of the model running the Gateway.
        https_mode: One of "disabled", "enabled", "enforced".
        hostnames: List of hostnames for the HTTPRoute.
        paths: List of path prefixes.
        backend_service_name: Name of the K8s Service to route traffic to.
        backend_service_port: Port of the backend Service.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    managed_names = []

    # HTTP route: a single route covering all hostnames, attaching to every
    # per-hostname HTTP listener via multiple parentRefs. When there are no
    # hostnames, fall back to the single hostname-less HTTP listener (mirrors
    # the gateway-api-integrator's empty-hostnames listener fallback).
    if hostnames:
        http_listener_names = [
            http_listener_name(gateway_name, hostname) for hostname in hostnames
        ]
    else:
        http_listener_names = [f"{gateway_name}-http"]

    http_config = HTTPRouteConfig(
        app_name=app_name,
        scheme="http",
        gateway_name=gateway_name,
        gateway_namespace=gateway_model,
        listener_names=http_listener_names,
        hostnames=hostnames,
        paths=paths,
        backend_service_name=backend_service_name,
        backend_service_port=backend_service_port,
        redirect_https=https_mode == "enforced",
    )
    managed_names.append(http_route_manager.apply(http_config))

    # HTTPS routes: one per hostname, each targeting its own per-hostname listener.
    if https_mode in ("enabled", "enforced"):
        for hostname in hostnames:
            https_config = HTTPRouteConfig(
                app_name=app_name,
                scheme="https",
                gateway_name=gateway_name,
                gateway_namespace=gateway_model,
                listener_names=[https_listener_name(gateway_name, hostname)],
                hostnames=[hostname],
                paths=paths,
                backend_service_name=backend_service_name,
                backend_service_port=backend_service_port,
                redirect_https=False,
            )
            managed_names.append(http_route_manager.apply(https_config))

    http_route_manager.delete_stale(exclude=managed_names)
