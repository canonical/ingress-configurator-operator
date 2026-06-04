# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers and common utilities for the ingress-configurator-operator states."""

import logging
from typing import Annotated, Literal, Self, cast

import ops
from annotated_types import Len
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import Field, IPvAnyAddress, ValidationError
from pydantic.dataclasses import dataclass

from helpers import get_invalid_config_fields

logger = logging.getLogger(__name__)


class InvalidStateError(Exception):
    """Exception raised when the state is invalid."""


class InvalidBackendStateError(InvalidStateError):
    """Exception raised when the backend configuration is invalid."""


@dataclass(frozen=True)
class BackendState:
    """Charm state subset that contains the backend configuration.

    Attributes:
        backend_addresses: Configured list of backend ip addresses.
        backend_ports: Configured list of backend ports.
        backend_protocol: The configured protocol for the backend.
    """

    backend_addresses: Annotated[list[IPvAnyAddress], Len(min_length=1)]
    backend_ports: Annotated[list[Annotated[int, Field(gt=0, le=65535)]], Len(min_length=1)]
    backend_protocol: Literal["http", "https"]

    @classmethod
    def has_integrator_config(cls, charm: ops.CharmBase) -> bool:
        """Return True if any integrator backend config option is set.

        This is intentionally a presence check — it does not validate the values.
        Use it to detect ambiguous mode (ingress relation + backend config both
        present) before attempting to parse the config with for_integrator_mode.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            True if backend-addresses or backend-ports is set in config.
        """
        return bool(charm.config.get("backend-addresses") or charm.config.get("backend-ports"))

    @classmethod
    def for_integrator_mode(cls, charm: ops.CharmBase) -> Self:
        """Create BackendState for integrator mode from charm config.

        Args:
            charm: the ingress-configurator charm.

        Raises:
            InvalidHaproxyRouteStateError: when backend config is missing or invalid.

        Returns:
            BackendState: instance of the backend state.
        """
        try:
            config_backend_addresses = (
                [
                    cast(IPvAnyAddress, address)
                    for address in cast(str, charm.config.get("backend-addresses")).split(",")
                ]
                if charm.config.get("backend-addresses")
                else []
            )
            config_backend_ports = (
                [int(port) for port in cast(str, charm.config.get("backend-ports")).split(",")]
                if charm.config.get("backend-ports")
                else []
            )
            backend_protocol = cast(
                Literal["http", "https"], charm.config.get("backend-protocol", "http")
            )
            return cls(config_backend_addresses, config_backend_ports, backend_protocol)
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidBackendStateError(
                f"Invalid integrator backend configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidBackendStateError("Backend state contains invalid value(s).") from exc

    @classmethod
    def for_adapter_mode(
        cls,
        charm: ops.CharmBase,
        ingress_data: IngressRequirerData,
    ) -> Self:
        """Create BackendState for adapter mode from ingress requirer data.

        Args:
            charm: the ingress-configurator charm.
            ingress_data: the ingress requirer relation data.

        Raises:
            InvalidBackendStateError: when the configuration is invalid.

        Returns:
            BackendState: instance of the backend state.
        """
        try:
            backend_addresses = [cast(IPvAnyAddress, unit.ip) for unit in ingress_data.units]
            backend_ports = [ingress_data.app.port]
            backend_protocol = cast(
                Literal["http", "https"],
                (charm.config.get("backend-protocol") or "http"),
            )
            return cls(backend_addresses, backend_ports, backend_protocol)
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidBackendStateError(
                f"Invalid adapter backend configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidBackendStateError("Backend state contains invalid value(s).") from exc
