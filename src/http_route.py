# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""HTTPRoute resource management for gateway-route mode."""

import dataclasses
import logging

from lightkube import ApiError, Client
from lightkube.generic_resource import create_namespaced_resource
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.discovery_v1 import Endpoint, EndpointPort
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Service
from lightkube.resources.discovery_v1 import EndpointSlice

from kubernetes import InvalidKubernetesPermissionError

logger = logging.getLogger(__name__)

CUSTOM_RESOURCE_GROUP_NAME = "gateway.networking.k8s.io"
HTTP_ROUTE_RESOURCE_NAME = "HTTPRoute"
HTTP_ROUTE_PLURAL = "httproutes"
MANAGED_BY_LABEL = "ingress-configurator.charm.juju.is/managed-by"


HTTPRouteResource = create_namespaced_resource(
    CUSTOM_RESOURCE_GROUP_NAME, "v1", HTTP_ROUTE_RESOURCE_NAME, HTTP_ROUTE_PLURAL
)


def apply_headless_backend(
    client: Client,
    namespace: str,
    name: str,
    addresses: list[str],
    port: int,
    app_name: str,
) -> None:
    """Create or update a headless Service and its associated EndpointSlice.

    Both resources share ``name`` and are labelled with :data:`MANAGED_BY_LABEL`
    so they can be found and cleaned up later.

    Args:
        client: The lightkube Client instance.
        namespace: The Kubernetes namespace to create resources in.
        name: Name for both the Service and the EndpointSlice.
        addresses: FQDNs for the endpoints.
        port: The port to expose.
        app_name: Owning charm name, used as the value of the :data:`MANAGED_BY_LABEL` label.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    service = Service(
        metadata=ObjectMeta(
            name=name,
            namespace=namespace,
            labels={MANAGED_BY_LABEL: app_name},
        ),
        spec=ServiceSpec(
            clusterIP="None",
            ports=[ServicePort(port=port)],
        ),
    )
    try:
        client.apply(service, field_manager=app_name, force=True)
    except ApiError as e:
        if e.status.code == 403:
            raise InvalidKubernetesPermissionError(
                "This charm needs --trust to run on k8s substrates"
            ) from e
        raise

    if not addresses:
        return

    endpoint_slice = EndpointSlice(
        addressType="FQDN",
        metadata=ObjectMeta(
            name=name,
            namespace=namespace,
            labels={
                "kubernetes.io/service-name": name,
                MANAGED_BY_LABEL: app_name,
            },
        ),
        endpoints=[Endpoint(addresses=[addr]) for addr in addresses],
        ports=[EndpointPort(port=port)],
    )
    try:
        client.apply(endpoint_slice, field_manager=app_name, force=True)
    except ApiError as e:
        if e.status.code == 403:
            raise InvalidKubernetesPermissionError(
                "This charm needs --trust to run on k8s substrates"
            ) from e
        raise


def delete_headless_backends_owned_by(
    client: Client,
    namespace: str,
    app_name: str,
) -> None:
    """Delete all headless EndpointSlices and Services owned by ``app_name``.

    Resources are identified by a :data:`MANAGED_BY_LABEL` label matching ``app_name``.

    Args:
        client: The lightkube Client instance.
        namespace: The Kubernetes namespace to search in.
        app_name: The owning charm name to match.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    try:
        for es in client.list(
            EndpointSlice, namespace=namespace, labels={MANAGED_BY_LABEL: app_name}
        ):
            if es.metadata and es.metadata.name:
                client.delete(EndpointSlice, name=es.metadata.name, namespace=namespace)
        for service in client.list(
            Service, namespace=namespace, labels={MANAGED_BY_LABEL: app_name}
        ):
            if service.metadata and service.metadata.name:
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
        listener_name: sectionName (e.g. "<gateway_name>-http-listener").
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
    listener_name: str
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
        parent_ref: dict[str, str] = {
            "name": config.gateway_name,
            "namespace": config.gateway_namespace,
            "sectionName": config.listener_name,
        }

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
            "parentRefs": [parent_ref],
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
        resource_name = f"{config.app_name}-{config.backend_service_name}-{config.scheme}"
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
        except ApiError:
            logger.exception("Error cleaning up stale HTTPRoutes")


def create_http_routes(
    http_route_manager: HTTPRouteManager,
    app_name: str,
    backend_app_name: str,
    gateway_name: str,
    gateway_model: str,
    https_mode: str,
    hostnames: list[str],
    paths: list[str],
    backend_service_port: int,
    is_port_open: bool,
    backend_addresses: list[str],
) -> None:
    """Create HTTPRoute K8s resources based on https_mode.

    Resolves the backend Service name (creating a headless Service/EndpointSlice
    when the workload port is not yet open) before applying the HTTPRoute resources.

    Args:
        http_route_manager: The HTTPRouteManager to apply and clean up resources.
        app_name: Charm application name used in managed HTTPRoute resource names
            and as the value of the :data:`MANAGED_BY_LABEL` label on headless resources.
        backend_app_name: Backend workload application name, used to resolve the
            backend Service (its Kubernetes Service name matches this when the port
            is open).
        gateway_name: Name of the Gateway K8s resource.
        gateway_model: Name of the model running the Gateway.
        https_mode: One of "disabled", "enabled", "enforced".
        hostnames: List of hostnames for the HTTPRoute.
        paths: List of path prefixes.
        backend_service_port: Port of the backend Service.
        is_port_open: Whether the backend workload has opened the ingress port.
        backend_addresses: Unit hosts used when falling back to a headless Service.

    Raises:
        InvalidKubernetesPermissionError: When the charm lacks RBAC permissions.
    """
    if is_port_open:
        delete_headless_backends_owned_by(
            http_route_manager.client, http_route_manager.namespace, app_name
        )
        backend_service_name = backend_app_name
    else:
        headless_name = f"{app_name}-{backend_app_name}-headless"
        apply_headless_backend(
            http_route_manager.client,
            http_route_manager.namespace,
            headless_name,
            backend_addresses,
            backend_service_port,
            app_name,
        )
        backend_service_name = headless_name
    managed_names = []

    route_specs: list[str] = ["http"]
    if https_mode in ("enabled", "enforced"):
        route_specs.append("https")

    for scheme in route_specs:
        config = HTTPRouteConfig(
            app_name=app_name,
            scheme=scheme,
            gateway_name=gateway_name,
            gateway_namespace=gateway_model,
            listener_name=f"{gateway_name}-{scheme}-listener",
            hostnames=hostnames,
            paths=paths,
            backend_service_name=backend_service_name,
            backend_service_port=backend_service_port,
            redirect_https=https_mode == "enforced" and scheme == "http",
        )
        managed_names.append(http_route_manager.apply(config))

    http_route_manager.delete_stale(exclude=managed_names)
