# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import logging
from typing import Annotated, cast

import ops
from annotated_types import Len
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from validators import get_invalid_config_fields, value_has_valid_characters

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","


class InvalidStateError(Exception):
    """Exception raised when the state is invalid."""


@dataclass(frozen=True)
class BackendState:
    """Charm state subset that contains the backend configuration.

    Attributes:
        backend_addresses: Configured list of backend ip addresses.
        backend_ports: Configured list of backend ports.
    """

    backend_addresses: Annotated[list[IPvAnyAddress], Len(min_length=1)]
    backend_ports: Annotated[list[Annotated[int, Field(gt=0, le=65535)]], Len(min_length=1)]


@dataclass(frozen=True)
class State:
    """Charm state that contains the configuration.

    Attributes:
        backend_addresses: Configured list of backend ip addresses.
        backend_ports: Configured list of backend ports.
        service: The service name.
        retry_count: Number of times to retry failed requests.
        retry_interval: Interval between retries in seconds.
        retry_redispatch: Whether to redispatch failed requests to another server.
        paths: List of URL paths to route to the service.
        subdomains: List of subdomains to route to the service.
    """

    _backend_state: BackendState
    service: str = Field(..., min_length=1)
    retry_count: int | None = Field(gt=0)
    retry_interval: int | None = Field(gt=0)
    retry_redispatch: bool | None = False
    paths: list[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(default=[])
    subdomains: list[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(
        default=[]
    )

    @property
    def backend_addresses(self) -> list[IPvAnyAddress]:
        """List of backend addresses."""
        return self._backend_state.backend_addresses

    @property
    def backend_ports(self) -> list[int]:
        """List of backend ports."""
        return self._backend_state.backend_ports

    @classmethod
    # pylint: disable=too-many-locals
    def from_charm(cls, charm: ops.CharmBase, ingress_data: IngressRequirerData | None) -> "State":
        """Create an State class from a charm instance.

        Args:
            charm: the ingress-configurator charm.
            ingress_data: the ingress requirer relation data.

        Raises:
            InvalidStateError: when the integrator mode config is invalid.

        Returns:
            State: instance of the state component.
        """
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
        ingress_backend_ports = [ingress_data.app.port] if ingress_data else []
        ingress_backend_addresses = (
            [cast(IPvAnyAddress, unit.ip) for unit in ingress_data.units] if ingress_data else []
        )
        paths = (
            cast(str, charm.config.get("paths")).split(CHARM_CONFIG_DELIMITER)
            if charm.config.get("paths")
            else []
        )
        retry_count = (
            cast(int, charm.config.get("retry-count")) if charm.config.get("retry-count") else None
        )
        retry_interval = (
            cast(int, charm.config.get("retry-interval"))
            if charm.config.get("retry-interval")
            else None
        )
        retry_redispatch = (
            cast(bool, charm.config.get("retry-redispatch"))
            if charm.config.get("retry-redispatch")
            else None
        )
        subdomains = (
            cast(str, charm.config.get("subdomains")).split(CHARM_CONFIG_DELIMITER)
            if charm.config.get("subdomains")
            else []
        )
        try:
            config_backend = config_backend_addresses or config_backend_ports
            ingress_backend = ingress_backend_addresses or ingress_backend_ports
            # Only backend configuration from a single origin is supported
            if config_backend == ingress_backend:
                raise InvalidStateError("No valid mode detected.")
            backend_addresses = config_backend_addresses or ingress_backend_addresses
            backend_ports = config_backend_ports or ingress_backend_ports
            return cls(
                _backend_state=BackendState(backend_addresses, backend_ports),
                paths=paths,
                retry_count=retry_count,
                retry_interval=retry_interval,
                retry_redispatch=retry_redispatch,
                service=f"{charm.model.name}-{charm.app.name}",
                subdomains=subdomains,
            )
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidStateError(
                f"Invalid integrator configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidStateError("State contains invalid value(s).") from exc
