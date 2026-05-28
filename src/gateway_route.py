# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""HTTPRoute resource management for gateway-route mode."""

import dataclasses
import logging

from lightkube import ApiError, Client
from lightkube.generic_resource import create_namespaced_resource

logger = logging.getLogger(__name__)

CUSTOM_RESOURCE_GROUP_NAME = "gateway.networking.k8s.io"
HTTP_ROUTE_RESOURCE_NAME = "HTTPRoute"
HTTP_ROUTE_PLURAL = "httproutes"

HTTPRouteResource = create_namespaced_resource(
    CUSTOM_RESOURCE_GROUP_NAME, "v1", HTTP_ROUTE_RESOURCE_NAME, HTTP_ROUTE_PLURAL
)


@dataclasses.dataclass
class HTTPRouteConfig:
    """Configuration for an HTTPRoute resource.

    Attributes:
        name: Resource name.
        gateway_name: parentRef gateway name.
        gateway_namespace: parentRef namespace.
        listener_name: sectionName (e.g. "<gateway_name>-http-listener").
        hostnames: List of hostnames for the HTTPRoute.
        paths: List of path prefixes.
        backend_service_name: The workload K8s Service name.
        backend_service_port: The workload port.
        redirect_https: If True, this route issues a 301 HTTPS redirect.
    """

    name: str
    gateway_name: str
    gateway_namespace: str
    listener_name: str
    hostnames: list[str]
    paths: list[str]
    backend_service_name: str
    backend_service_port: int
    redirect_https: bool = False


class InsufficientPermissionError(Exception):
    """Raised when the charm lacks K8s RBAC permissions to manage HTTPRoutes."""


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
    def _build_spec(config: HTTPRouteConfig) -> dict:
        """Build the HTTPRoute spec dict from a config.

        Args:
            config: The HTTPRoute configuration.

        Returns:
            A dict representing the HTTPRoute spec.
        """
        parent_ref: dict = {
            "name": config.gateway_name,
            "namespace": config.gateway_namespace,
            "sectionName": config.listener_name,
        }

        if config.redirect_https:
            rules = [
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
            InsufficientPermissionError: When the charm lacks RBAC permissions (403).

        Returns:
            The resource name.
        """
        spec = self._build_spec(config)
        resource = HTTPRouteResource(
            metadata={
                "name": config.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            spec=spec,
        )
        try:
            self.client.apply(resource, field_manager="ingress-configurator", force=True)
        except ApiError as e:
            if e.status.code == 403:
                raise InsufficientPermissionError(
                    "This charm needs `juju trust` to manage HTTPRoute resources"
                ) from e
            raise
        logger.info("Applied HTTPRoute %s", config.name)
        return config.name

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
                if name not in exclude_set:
                    self.client.delete(HTTPRouteResource, name=name, namespace=self.namespace)
                    logger.info("Deleted stale HTTPRoute %s", name)
        except ApiError:
            logger.exception("Error cleaning up stale HTTPRoutes")
