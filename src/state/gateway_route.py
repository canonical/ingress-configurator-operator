# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Gateway route state management module."""

import logging
from typing import Annotated, Self, cast

import ops
from charms.gateway_api_integrator.v1.gateway_route import valid_fqdn
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError, field_validator, model_validator
from pydantic.dataclasses import dataclass

from helpers import get_invalid_config_fields

logger = logging.getLogger(__name__)

CHARM_CONFIG_DELIMITER = ","


class InvalidGatewayRouteStateError(Exception):
    """Exception raised when GatewayRouteState contains invalid attributes."""


@dataclass(frozen=True)
class GatewayRouteState:
    """State for the gateway-route reconcile path.

    Attributes:
        application_name: Name of the backend application (from ingress relation).
        model_name: Model the backend application is in (from ingress relation).
        backend_port: Port the backend application listens on (from ingress relation).
        is_port_open: Whether the backend application has opened the required port.
        backend_addresses: Unit hostnames (FQDNs) to use when is_port_open is False.
        backend_protocol: Protocol used to reach the backend (must not be 'https').
        hostname: Optional hostname to route traffic to.
        additional_hostnames: Additional hostnames to route traffic to.
        paths: URL path prefixes to route.
    """

    application_name: str
    model_name: str
    hostname: Annotated[str, BeforeValidator(valid_fqdn)] | None
    backend_port: int = Field(gt=0, le=65535)
    is_port_open: bool = False
    backend_addresses: list[Annotated[str, BeforeValidator(valid_fqdn)]] = Field(
        default_factory=list
    )
    backend_protocol: str = "http"
    additional_hostnames: list[Annotated[str, BeforeValidator(valid_fqdn)]] = Field(
        default_factory=list
    )
    paths: list[str] = Field(default_factory=lambda: ["/"])

    @field_validator("backend_protocol")
    @classmethod
    def validate_backend_protocol(cls, value: str) -> str:
        """Ensure backend_protocol is not 'https'.

        Raises:
            ValueError: If the value is 'https'.
        """
        if value == "https":
            raise ValueError("backend-protocol cannot be 'https' in gateway-route mode")
        return value

    @model_validator(mode="after")
    def validate_backend_configuration(self) -> Self:
        """Ensure that the backend configuration is valid.

        Raises:
            InvalidGatewayRouteStateError: If the configuration is invalid.
        """
        if self.is_port_open:
            return self

        if not self.backend_addresses:
            raise ValueError(
                "Invalid backend configuration: port is not open and no backend addresses provided."
            )

        return self

    @classmethod
    def build_for_adapter_mode(
        cls, charm: ops.CharmBase, ingress_data: IngressRequirerData
    ) -> Self:
        """Create a GatewayRouteState from charm config and ingress relation data.

        Args:
            charm: The charm instance.
            ingress_data: Validated data from the ingress relation.

        Raises:
            InvalidGatewayRouteStateError: When config values are invalid.

        Returns:
            GatewayRouteState instance.
        """
        hostname = cast(str, charm.config.get("hostname"))
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
                application_name=ingress_data.app.name,
                model_name=ingress_data.app.model,
                backend_port=ingress_data.app.port,
                is_port_open=ingress_data.app.is_port_open,
                backend_addresses=[u.host for u in ingress_data.units],
                backend_protocol=cast(str, charm.config.get("backend-protocol") or "http"),
                hostname=hostname,
                additional_hostnames=additional_hostnames,
                paths=paths,
            )
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ", ".join(get_invalid_config_fields(exc))
            raise InvalidGatewayRouteStateError(
                f"Invalid gateway-route configuration: {error_field_str}"
            ) from exc

    @property
    def hostnames(self) -> list[str]:
        """All hostnames: primary + additional.

        Returns:
            List of all hostnames, including the primary and additional hostnames.
        """
        primary = [self.hostname] if self.hostname else []
        return primary + self.additional_hostnames
