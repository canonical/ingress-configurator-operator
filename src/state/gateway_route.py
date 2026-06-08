# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Gateway route state management module."""

import logging
from typing import Annotated, Self, cast

import ops
from charms.gateway_api_integrator.v1.gateway_route import valid_fqdn
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError
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
        port: Port the backend application listens on (from ingress relation).
        hostname: Optional hostname to route traffic to.
        additional_hostnames: Additional hostnames to route traffic to.
        paths: URL path prefixes to route.
    """

    application_name: str
    model_name: str
    hostname: Annotated[str, BeforeValidator(valid_fqdn)]
    port: int = Field(gt=0, le=65535)
    additional_hostnames: list[Annotated[str, BeforeValidator(valid_fqdn)]] = Field(default=[])
    paths: list[str] = Field(default=["/"])

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

        if charm.config.get("backend-protocol") == "https":
            raise InvalidGatewayRouteStateError(
                "backend-protocol cannot be 'https' in gateway-route mode"
            )

        try:
            return cls(
                application_name=ingress_data.app.name,
                model_name=ingress_data.app.model,
                port=ingress_data.app.port,
                hostname=hostname,
                additional_hostnames=additional_hostnames,
                paths=paths,
            )
        except ValidationError as exc:
            invalid_fields = get_invalid_config_fields(exc)
            logger.error("Invalid gateway-route configuration: %s", invalid_fields)
            raise InvalidGatewayRouteStateError(
                f"Invalid gateway-route configuration: {', '.join(str(f) for f in invalid_fields)}"
            ) from exc

    @property
    def hostnames(self) -> list[str]:
        """All hostnames: primary + additional.

        Returns:
            List of all hostnames, including the primary and additional hostnames.
        """
        return [self.hostname, *self.additional_hostnames]
