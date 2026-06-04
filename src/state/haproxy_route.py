# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import logging
from typing import Annotated, Literal, Optional, Self, cast

import ops
from annotated_types import Len
from charms.haproxy.v2.haproxy_route import (
    LoadBalancingAlgorithm,
    LoadBalancingConfiguration,
    Retry,
    TimeoutConfiguration,
    valid_domain_with_wildcard,
)
from charms.traefik_k8s.v2.ingress import IngressRequirerData
from pydantic import BeforeValidator, Field, ValidationError, model_validator
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from helpers import get_invalid_config_fields, value_has_valid_characters
from state.helpers import InvalidStateError

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","
DEFAULT_PATH_REWRITE_EXPRESSION_DELIMITER = ";"


class InvalidHaproxyRouteStateError(InvalidStateError):
    """Exception raised when HAProxy route requirements are invalid."""


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

    @classmethod
    def for_kubernetes_adapter_mode(
        cls,
        charm: ops.CharmBase,
        backend_addresses: list[IPvAnyAddress],
        backend_ports: list[int],
    ) -> Self:
        """Create BackendState from pre-resolved Kubernetes backend addresses and ports.

        Args:
            charm: the ingress-configurator charm.
            backend_addresses: resolved backend IP addresses.
            backend_ports: resolved backend ports.

        Raises:
            InvalidBackendStateError: when the configuration is invalid.

        Returns:
            BackendState: instance of the backend state.
        """
        try:
            backend_protocol = cast(
                Literal["http", "https"],
                charm.config.get("backend-protocol", "http"),
            )
            return cls(backend_addresses, backend_ports, backend_protocol)
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidBackendStateError(
                f"Invalid k8s adapter backend configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidBackendStateError("Backend state contains invalid value(s).") from exc


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
    def validate_health_check_all_set(self) -> Self:
        """Perform additional validations.

        Returns: this class instance.

        Raises:
            ValueError: if the validation doesn't pass.
        """
        all_or_none_health_checks_set = (
            (self.interval is None) == (self.rise is None) == (self.fall is None)
        )
        if not all_or_none_health_checks_set:
            raise ValueError(
                "Health check configuration is incomplete: interval, rise, and fall "
                "must all be set if any one of them is specified."
            )
        return self

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> Self:
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


# pylint: disable=too-many-instance-attributes,too-many-locals
@dataclass(frozen=True)
class HaproxyRouteState:
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
    retry: Retry | None
    timeout: TimeoutConfiguration
    service: str = Field(..., min_length=1)
    paths: list[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(default=[])
    hostname: Optional[Annotated[str, BeforeValidator(valid_domain_with_wildcard)]] = Field(
        default=None
    )
    additional_hostnames: list[Annotated[str, BeforeValidator(valid_domain_with_wildcard)]] = (
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
    def from_charm(
        cls,
        charm: ops.CharmBase,
        backend_state: BackendState,
        service: str,
    ) -> Self:
        """Build HaproxyRouteState from a resolved backend and charm config.

        Args:
            charm: the ingress-configurator charm.
            backend_state: pre-resolved backend configuration.
            service: the service name.

        Raises:
            InvalidHaproxyRouteStateError: when the configuration is invalid.

        Returns:
            HaproxyRouteState: instance of the state.
        """
        try:
            external_grpc_port = cast(int | None, charm.config.get("external-grpc-port"))
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
            retry_count = cast(int | None, charm.config.get("retry-count"))
            retry = (
                Retry(
                    count=retry_count,
                    redispatch=cast(bool, charm.config.get("retry-redispatch")),
                )
                if retry_count is not None
                else None
            )
            timeout = TimeoutConfiguration(
                **{
                    k: v
                    for k, v in {
                        "server": cast(int | None, charm.config.get("timeout-server")),
                        "connect": cast(int | None, charm.config.get("timeout-connect")),
                        "queue": cast(int | None, charm.config.get("timeout-queue")),
                    }.items()
                    if v is not None
                }
            )
            allow_http = cast(bool, charm.config.get("allow-http", False))
            return cls(
                _backend_state=backend_state,
                paths=paths,
                health_check=HealthCheck.from_charm(charm),
                retry=retry,
                timeout=timeout,
                service=service,
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
            raise InvalidHaproxyRouteStateError(
                f"Invalid configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidHaproxyRouteStateError("State contains invalid value(s).") from exc
