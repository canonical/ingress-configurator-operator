# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Gateway route state management module."""

from typing import Annotated, Literal, Self

import ops
from charms.gateway_api_integrator.v1.gateway_route import valid_fqdn
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, TypeAdapter, ValidationError, field_validator
from pydantic.dataclasses import dataclass
from pydantic_core import PydanticUseDefault

from helpers import InvalidRouteStateError, split_delimited


class InvalidGatewayRouteStateError(InvalidRouteStateError):
    """Exception raised when a GatewayRouteState contains invalid attributes."""


@dataclass(frozen=True)
class GatewayRouteState:
    """State for the gateway-route reconcile path.

    Attributes:
        application_name: Name of the backend application.
        model_name: Model/namespace for the backend application.
        backend_port: Port the backend application listens on.
        backend_protocol: Protocol used to reach the backend. Only ``"http"`` is supported.
        hostname: Optional hostname to route traffic to.
        additional_hostnames: Additional hostnames to route traffic to.
        paths: URL path prefixes to route.
        strip_prefix: Whether the matched path prefix should be rewritten to ``/``
            before the request reaches the backend.
    """

    application_name: str
    model_name: str
    hostname: Annotated[str, BeforeValidator(valid_fqdn)] | None
    backend_protocol: Literal["http"] | None
    backend_port: int = Field(gt=0, le=65535)
    additional_hostnames: Annotated[
        list[Annotated[str, BeforeValidator(valid_fqdn)]],
        BeforeValidator(split_delimited),
    ] = Field(default=[])
    paths: list[str] = Field(default=["/"])
    strip_prefix: bool = False

    @field_validator("paths", mode="before")
    @classmethod
    def parse_paths(cls, value: object) -> object:
        """Normalize configured paths, using the field default for empty raw config.

        Args:
            value: Raw comma-separated path config or an already-parsed list.

        Returns:
            Normalized paths for raw config, otherwise the original value.

        Raises:
            PydanticUseDefault: If raw config contains no nonempty paths.
        """
        if value is None or isinstance(value, str):
            paths = split_delimited(value)
            if not paths:
                raise PydanticUseDefault()
            return paths
        return value

    @property
    def hostnames(self) -> list[str]:
        """All hostnames: primary + additional.

        Returns:
            List of all hostnames, including the primary and additional hostnames.
        """
        return [self.hostname, *self.additional_hostnames] if self.hostname else []

    @staticmethod
    def has_integrator_config(charm: ops.CharmBase) -> bool:
        """Detect backend config that is unsupported with gateway-route.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            True if backend-addresses or backend-ports is set in config.
        """
        return bool(charm.config.get("backend-addresses") or charm.config.get("backend-ports"))

    @classmethod
    def _build(
        cls,
        charm: ops.CharmBase,
        application_name: str,
        model_name: str,
        backend_port: int,
        strip_prefix: bool = False,
    ) -> Self:
        """Build a GatewayRouteState from shared config.

        Args:
            charm: The charm instance.
            application_name: Name of the backend application.
            model_name: Model/namespace for the backend application.
            backend_port: Port the backend listens on.
            strip_prefix: Whether to rewrite the matched path prefix to ``/``.

        Raises:
            InvalidGatewayRouteStateError: When config values are invalid.

        Returns:
            GatewayRouteState instance.
        """
        try:
            return TypeAdapter(cls).validate_python(
                {
                    "application_name": application_name,
                    "model_name": model_name,
                    "backend_port": backend_port,
                    "backend_protocol": charm.config.get("backend-protocol"),
                    "hostname": charm.config.get("hostname"),
                    "additional_hostnames": charm.config.get("additional-hostnames"),
                    "paths": charm.config.get("paths"),
                    "strip_prefix": strip_prefix,
                }
            )
        except ValidationError as exc:
            raise InvalidGatewayRouteStateError(
                "Invalid gateway-route configuration", validation_error=exc
            ) from exc

    @classmethod
    def build_for_adapter_mode(
        cls, charm: ops.CharmBase, ingress_data: IngressRequirerData
    ) -> Self:
        """Create a GatewayRouteState for adapter mode from charm config and ingress data.

        Args:
            charm: The charm instance.
            ingress_data: Validated data from the ingress relation.

        Raises:
            InvalidGatewayRouteStateError: When config values are invalid.

        Returns:
            GatewayRouteState instance for adapter mode.
        """
        return cls._build(
            charm,
            application_name=ingress_data.app.name,
            model_name=ingress_data.app.model,
            backend_port=ingress_data.app.port,
            strip_prefix=bool(ingress_data.app.strip_prefix),
        )
