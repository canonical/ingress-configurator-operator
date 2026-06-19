# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Gateway route state management module."""

import ipaddress
import logging
from typing import Annotated, Literal, Self, cast

import ops
from annotated_types import Len
from charms.gateway_api_integrator.v1.gateway_route import valid_fqdn
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError
from pydantic.dataclasses import dataclass

from helpers import get_invalid_config_fields

logger = logging.getLogger(__name__)

CHARM_CONFIG_DELIMITER = ","


class InvalidGatewayRouteStateError(Exception):
    """Exception raised when a GatewayRouteState contains invalid attributes."""


@dataclass(frozen=True)
class GatewayRouteIntegratorSubState:
    """Additional state specific to gateway-route integrator mode.

    Attributes:
        backend_addresses: Backend IP addresses used to build a headless
            Service + EndpointSlice.
    """

    backend_addresses: Annotated[
        list[ipaddress.IPv4Address] | list[ipaddress.IPv6Address], Len(min_length=1)
    ] = Field(default_factory=lambda: [])

    @property
    def address_type(self) -> Literal["IPv4", "IPv6"]:
        """EndpointSlice addressType derived from the IP family of backend_addresses.

        Returns:
            "IPv4" or "IPv6".
        """
        return "IPv4" if isinstance(self.backend_addresses[0], ipaddress.IPv4Address) else "IPv6"


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
        integrator_state: Integrator-mode-specific state. Only populated for integrator mode.
    """

    application_name: str
    model_name: str
    hostname: Annotated[str, BeforeValidator(valid_fqdn)] | None
    backend_protocol: Literal["http"] | None
    backend_port: int = Field(gt=0, le=65535)
    additional_hostnames: list[Annotated[str, BeforeValidator(valid_fqdn)]] = Field(
        default_factory=lambda: []
    )
    paths: list[str] = Field(default_factory=lambda: ["/"])
    integrator_state: GatewayRouteIntegratorSubState | None = None

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
        integrator_state: GatewayRouteIntegratorSubState | None = None,
    ) -> Self:
        """Build a GatewayRouteState from shared config.

        Args:
            charm: The charm instance.
            application_name: Name of the backend application.
            model_name: Model/namespace for the backend application.
            backend_port: Port the backend listens on.
            integrator_state: Populated for integrator mode, None otherwise.

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
                integrator_state=integrator_state,
            )
        except ValidationError as exc:
            logger.error("Invalid gateway-route config fields: %s", get_invalid_config_fields(exc))
            raise InvalidGatewayRouteStateError(
                "Invalid gateway-route configuration."
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
        raw_addresses = cast(str, charm.config.get("backend-addresses") or "")
        addr_strings = [
            a.strip() for a in raw_addresses.split(CHARM_CONFIG_DELIMITER) if a.strip()
        ]

        raw_ports = cast(str, charm.config.get("backend-ports") or "")
        port_values = [p.strip() for p in raw_ports.split(CHARM_CONFIG_DELIMITER) if p.strip()]
        if len(port_values) != 1:
            raise InvalidGatewayRouteStateError(
                "gateway-route requires exactly one port in backend-ports."
            )
        try:
            backend_port = int(port_values[0])
        except ValueError as exc:
            raise InvalidGatewayRouteStateError(
                f"Invalid port value in backend-ports: '{port_values[0]}'."
            ) from exc

        try:
            integrator_state = GatewayRouteIntegratorSubState(
                backend_addresses=addr_strings,  # type: ignore[arg-type]
            )
        except ValidationError as exc:
            logger.error("Invalid gateway-route config fields: %s", get_invalid_config_fields(exc))
            raise InvalidGatewayRouteStateError(
                "Invalid gateway-route configuration."
            ) from exc

        return cls._build(
            charm,
            application_name=charm.app.name,
            model_name=charm.model.name,
            backend_port=backend_port,
            integrator_state=integrator_state,
        )
