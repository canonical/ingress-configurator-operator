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
class HealthCheck:
    """Charm state that contains the health check configuration.

    Attributes:
        path: The path to use for server health checks.
        port: The port to use for http-check.
        interval: Interval between health checks in seconds.
        rise: Number of successful health checks before server is considered up.
        fall: Number of failed health checks before server is considered down.
    """

    path: Annotated[str, BeforeValidator(value_has_valid_characters)] | None
    port: int | None = Field(gt=0, le=65536)
    interval: int | None = Field(gt=0)
    rise: int | None = Field(gt=0)
    fall: int | None = Field(gt=0)

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "HealthCheck":
        """Create an HealthCheck class from a charm instance.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            HealthCheck: instance of the health check component.
        """
        interval = (
            cast(int, charm.config.get("health-check-interval"))
            if charm.config.get("health-check-interval") is not None
            else None
        )
        rise = (
            cast(int, charm.config.get("health-check-rise"))
            if charm.config.get("health-check-rise") is not None
            else None
        )
        fall = (
            cast(int, charm.config.get("health-check-fall"))
            if charm.config.get("health-check-fall") is not None
            else None
        )
        path = (
            cast(str, charm.config.get("health-check-path"))
            if charm.config.get("health-check-path") is not None
            else None
        )
        port = (
            cast(int, charm.config.get("health-check-port"))
            if charm.config.get("health-check-port") is not None
            else None
        )
        return cls(interval=interval, rise=rise, fall=fall, path=path, port=port)


@dataclass(frozen=True)
class Timeout:
    """Charm state that contains the timeout configuration.

    Attributes:
        server: Timeout for requests from haproxy to backend servers in seconds.
        connect: Timeout for client requests to haproxy in seconds.
        queue: Timeout for requests waiting in queue in seconds.
    """

    server: int | None = Field(gt=0)
    connect: int | None = Field(gt=0)
    queue: int | None = Field(gt=0)

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "Timeout":
        """Create an Timeout class from a charm instance.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            Retry: instance of the timeout component.
        """
        server = (
            cast(int, charm.config.get("timeout-server"))
            if charm.config.get("timeout-server")
            else None
        )
        connect = (
            cast(int, charm.config.get("timeout-connect"))
            if charm.config.get("timeout-connect")
            else None
        )
        queue = (
            cast(int, charm.config.get("timeout-queue"))
            if charm.config.get("timeout-queue")
            else None
        )
        return cls(server=server, connect=connect, queue=queue)


@dataclass(frozen=True)
class Retry:
    """Charm state that contains the retry configuration.

    Attributes:
        count: Number of times to retry failed requests.
        interval: Interval between retries in seconds.
        redispatch: Whether to redispatch failed requests to another server.
    """

    count: int | None = Field(gt=0)
    interval: int | None = Field(gt=0)
    redispatch: bool | None = None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "Retry":
        """Create an Retry class from a charm instance.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            Retry: instance of the retry component.
        """
        count = (
            cast(int, charm.config.get("retry-count"))
            if charm.config.get("retry-count") is not None
            else None
        )
        interval = (
            cast(int, charm.config.get("retry-interval"))
            if charm.config.get("retry-interval") is not None
            else None
        )
        redispatch = (
            cast(bool, charm.config.get("retry-redispatch"))
            if charm.config.get("retry-redispatch") is not None
            else None
        )
        return cls(count=count, interval=interval, redispatch=redispatch)


@dataclass(frozen=True)
class State:
    """Charm state that contains the configuration.

    Attributes:
        backend_addresses: Configured list of backend ip addresses.
        backend_ports: Configured list of backend ports.
        health_check: Health check configuration.
        retry: Retry configuration.
        timeout: The timeout configuration.
        service: The service name.
        paths: List of URL paths to route to the service.
        subdomains: List of subdomains to route to the service.
    """

    _backend_state: BackendState
    health_check: HealthCheck
    retry: Retry
    timeout: Timeout
    service: str = Field(..., min_length=1)
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
                health_check=HealthCheck.from_charm(charm),
                retry=Retry.from_charm(charm),
                timeout=Timeout.from_charm(charm),
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
