# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Gateway route state management module."""

import logging
from typing import Annotated, Literal, Self, cast

import ops
from charms.gateway_api_integrator.v1.gateway_route import valid_fqdn
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, TypeAdapter, ValidationError, field_validator
from pydantic.dataclasses import dataclass

from helpers import InvalidRouteStateError
from state.validators import (
    normalize_trimmed_comma_separated,
    split_comma_separated,
    split_trimmed_comma_separated,
)


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
        BeforeValidator(split_comma_separated),
    ] = Field(default_factory=lambda: [])
    paths: list[str] = Field(default_factory=lambda: ["/"])
    strip_prefix: bool = False

    @property
    def hostnames(self) -> list[str]:
        """All hostnames: primary + additional.

        Returns:
            List of all hostnames, including the primary and additional hostnames.
        """
        return [self.hostname, *self.additional_hostnames] if self.hostname else []

    @staticmethod
    def has_integrator_config(charm: ops.CharmBase) -> bool:
        """Return True if any gateway-route integrator backend config option is set.

        This is intentionally a presence check — it does not validate the values.
        Use it to detect the absence of backend configuration before attempting
        to parse the config with `build_for_integrator_mode`.

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
        hostname = cast(str | None, charm.config.get("hostname"))
        additional_hostnames = (
            cast(str, charm.config.get("additional-hostnames")).split(CHARM_CONFIG_DELIMITER)
            if charm.config.get("additional-hostnames")
            else []
        )
        paths_raw = (
            cast(str, charm.config.get("paths")).split(CHARM_CONFIG_DELIMITER)
            if charm.config.get("paths")
            else ["/"]
        )
        paths = [p.strip() for p in paths_raw if p.strip()] or ["/"]

        try:
            return cls(
                application_name=application_name,
                model_name=model_name,
                backend_port=backend_port,
                backend_protocol=cast(
                    Literal["http"] | None, charm.config.get("backend-protocol")
                ),
                hostname=hostname,
                additional_hostnames=additional_hostnames,
                paths=paths,
                strip_prefix=strip_prefix,
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

    @classmethod
    def build_for_integrator_mode(cls, charm: ops.CharmBase) -> Self:
        """Create a GatewayRouteState for integrator mode from charm config.

        In integrator mode there is no ingress relation. Traffic is routed to
        external backend IPs via a headless Service and EndpointSlice.

        Args:
            charm: The charm instance.

        Raises:
            InvalidGatewayRouteStateError: When config values are missing or invalid.

        Returns:
            GatewayRouteState instance with integrator_state populated.
        """
        return cls._build(
            charm,
            application_name=charm.app.name,
            model_name=charm.model.name,
            backend_port=cast(str | None, charm.config.get("backend-ports")),
            integrator_state={"backend_addresses": charm.config.get("backend-addresses")},
        )
