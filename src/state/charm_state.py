# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import logging
from typing import Annotated, Literal, Optional, Self, cast

import ops
from annotated_types import Len
from charms.haproxy.v1.haproxy_route import LoadBalancingAlgorithm, LoadBalancingConfiguration
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError, model_validator
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from validators import get_invalid_config_fields, value_has_valid_characters

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","
DEFAULT_PATH_REWRITE_EXPRESSION_DELIMITER = ";"


class InvalidStateError(Exception):
    """Exception raised when the state is invalid."""


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

    path: Optional[Annotated[str, BeforeValidator(value_has_valid_characters)]]
    port: Optional[int] = Field(gt=0, le=65536)
    interval: Optional[int] = Field(gt=0)
    rise: Optional[int] = Field(gt=0)
    fall: Optional[int] = Field(gt=0)

    @model_validator(mode="after")
    def validate_health_check_all_set(self) -> "HealthCheck":
        """Perform additional validations.

        Returns: this class instance.

        Raises:
            ValueError: if the validation doesn't pass.
        """
        all_or_none_health_checks_set = bool(self.interval) == bool(self.rise) == bool(self.fall)
        if not all_or_none_health_checks_set:
            raise ValueError(
                "Health check configuration is incomplete: interval, rise, and fall "
                "must all be set if any one of them is specified."
            )
        return self

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "HealthCheck":
        """Create an HealthCheck class from a charm instance.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            HealthCheck: instance of the health check component.
        """
        return cls(
            interval=cast(Optional[int], charm.config.get("health-check-interval")),
            rise=cast(Optional[int], charm.config.get("health-check-rise")),
            fall=cast(Optional[int], charm.config.get("health-check-fall")),
            path=cast(Optional[str], charm.config.get("health-check-path")),
            port=cast(Optional[int], charm.config.get("health-check-port")),
        )


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
        redispatch: Whether to redispatch failed requests to another server.
    """

    count: Optional[int] = Field(gt=0)
    redispatch: Optional[bool] = None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase, prefix: str = "") -> "Retry":
        """Create an Retry class from a charm instance.

        Args:
            charm: the ingress-configurator charm.
            prefix: prefix for the configuration option.

        Returns:
            Retry: instance of the retry component.
        """
        return cls(
            count=cast(Optional[int], charm.config.get(f"{prefix}retry-count")),
            redispatch=cast(Optional[bool], charm.config.get(f"{prefix}retry-redispatch")),
        )


# pylint: disable=too-many-instance-attributes,too-many-locals
@dataclass(frozen=True)
class State:
    """Charm state that contains the configuration.

    Attributes:
        backend_addresses: Configured list of backend ip addresses.
        backend_ports: Configured list of backend ports.
        backend_protocol: The configured protocol for the backend.
        health_check: Health check configuration.
        retry: Retry configuration.
        timeout: The timeout configuration.
        service: The service name.
        paths: List of URL paths to route to the service.
        hostname: The hostname to route to the service.
        additional_hostnames: List of additional hostnames to route to the service.
        load_balancing_configuration: Load balancing configuration.
        http_server_close: Configure server close after request.
        path_rewrite_expressions: List of path rewrite expressions.
        header_rewrite_expressions: List of header rewrite expressions.
        allow_http: Whether to allow HTTP traffic to the service.
        external_grpc_port: Optional gRPC external port.
    """

    _backend_state: BackendState
    health_check: HealthCheck
    retry: Retry
    timeout: Timeout
    service: str = Field(..., min_length=1)
    paths: list[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(default=[])
    hostname: Optional[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(
        default=None
    )
    additional_hostnames: list[Annotated[str, BeforeValidator(value_has_valid_characters)]] = (
        Field(default=[])
    )
    load_balancing_configuration: LoadBalancingConfiguration = Field(
        default=LoadBalancingConfiguration()
    )
    http_server_close: bool = Field(default=False)
    path_rewrite_expressions: list[str] = Field(default=[])
    header_rewrite_expressions: list[tuple[str, str]] = Field(default=[])
    allow_http: bool = Field(default=False)
    external_grpc_port: int | None = Field(default=None, gt=0, le=65535)

    @property
    def backend_addresses(self) -> list[IPvAnyAddress]:
        """List of backend addresses."""
        return self._backend_state.backend_addresses

    @property
    def backend_ports(self) -> list[int]:
        """List of backend ports."""
        return self._backend_state.backend_ports

    @property
    def backend_protocol(self) -> Literal["http", "https"]:
        """The backend protocol."""
        return self._backend_state.backend_protocol

    @model_validator(mode="after")
    def validate_external_grpc_port_requires_https(self) -> Self:
        """Perform additional validations.

        Returns: this class instance.

        Raises:
            ValueError: if the validation doesn't pass.
        """
        if self.external_grpc_port is not None and self.backend_protocol != "https":
            msg = "external_grpc_port can only be set when backend_protocol is 'https'."
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def validate_external_grpc_port_and_not_allow_http(self) -> Self:
        """Perform additional validations.

        Returns: this class instance.

        Raises:
            ValueError: if the validation doesn't pass.
        """
        if self.external_grpc_port is not None and self.allow_http:
            msg = "external_grpc_port cannot be set when allow_http is True."
            raise ValueError(msg)

        return self

    @classmethod
    def from_charm(cls, charm: ops.CharmBase, ingress_data: IngressRequirerData | None) -> Self:
        """Create an State class from a charm instance.

        Args:
            charm: the ingress-configurator charm.
            ingress_data: the ingress requirer relation data.

        Raises:
            InvalidStateError: when the integrator mode config is invalid.

        Returns:
            State: instance of the state component.
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
            # The value will be validated by the BackendState constructor
            backend_protocol = cast(
                Literal["http", "https"],
                (charm.config.get("backend-protocol") or "http"),
            )
            external_grpc_port = cast(int | None, charm.config.get("external-grpc-port"))
            ingress_backend_ports = [ingress_data.app.port] if ingress_data else []
            ingress_backend_addresses = (
                [cast(IPvAnyAddress, unit.ip) for unit in ingress_data.units]
                if ingress_data
                else []
            )
            paths = (
                cast(str, charm.config.get("paths")).split(CHARM_CONFIG_DELIMITER)
                if charm.config.get("paths")
                else []
            )
            hostname = cast(Optional[str], charm.config.get("hostname"))
            additional_hostnames = (
                cast(str, charm.config.get("additional-hostnames")).split(CHARM_CONFIG_DELIMITER)
                if charm.config.get("additional-hostnames")
                else []
            )
            http_server_close = cast(bool, charm.config.get("http-server-close", False))

            config_backend = bool(config_backend_addresses or config_backend_ports)
            ingress_backend = bool(ingress_backend_addresses or ingress_backend_ports)
            # Only backend configuration from a single origin is supported
            if config_backend == ingress_backend:
                raise InvalidStateError("No valid mode detected.")
            backend_addresses = config_backend_addresses or ingress_backend_addresses
            backend_ports = config_backend_ports or ingress_backend_ports

            load_balancing_algorithm = LoadBalancingAlgorithm(
                cast(
                    Optional[str],
                    charm.config.get(
                        "load-balancing-algorithm", LoadBalancingAlgorithm.LEASTCONN.value
                    ),
                )
            )
            load_balancing_configuration = LoadBalancingConfiguration(
                algorithm=load_balancing_algorithm,
                cookie=cast(Optional[str], charm.config.get("load-balancing-cookie")),
                consistent_hashing=cast(
                    bool, charm.config.get("load-balancing-consistent-hashing", False)
                ),
            )
            path_rewrite_expressions = (
                # The new line character ('\n') is escaped ('\\n') as set by the
                # configuration option
                cast(str, charm.config.get("path-rewrite-expressions")).split("\\n")
                if charm.config.get("path-rewrite-expressions")
                else []
            )
            header_rewrite_expressions = (
                # The new line character ('\n') is escaped ('\\n') as set by the
                # configuration option
                [
                    cast(tuple[str, str], tuple(elem.split(":", 1)))
                    for elem in cast(str, charm.config.get("header-rewrite-expressions")).split(
                        "\\n"
                    )
                ]
                if charm.config.get("header-rewrite-expressions")
                else []
            )
            allow_http = cast(bool, charm.config.get("allow-http", False))
            return cls(
                _backend_state=BackendState(backend_addresses, backend_ports, backend_protocol),
                paths=paths,
                health_check=HealthCheck.from_charm(charm),
                retry=Retry.from_charm(charm),
                timeout=Timeout.from_charm(charm),
                service=f"{charm.model.name}-{charm.app.name}",
                hostname=hostname,
                additional_hostnames=additional_hostnames,
                load_balancing_configuration=load_balancing_configuration,
                http_server_close=http_server_close,
                path_rewrite_expressions=path_rewrite_expressions,
                header_rewrite_expressions=header_rewrite_expressions,
                allow_http=allow_http,
                external_grpc_port=external_grpc_port,
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
