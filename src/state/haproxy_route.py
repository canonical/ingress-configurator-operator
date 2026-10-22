# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""HAProxy route state management module.

This module provides state management functionality for HAProxy routes
in the ingress configurator operator.
"""

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
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic.dataclasses import dataclass
from pydantic.json_schema import JsonSchemaValue
from pydantic.networks import IPvAnyAddress

from helpers import InvalidRouteStateError, split_delimited, value_has_valid_characters
from state.kubernetes import NodePortState

DEFAULT_PATH_REWRITE_EXPRESSION_DELIMITER = ";"


class InvalidHaproxyRouteStateError(InvalidRouteStateError):
    """Exception raised when HAProxy route requirements are invalid."""

    @staticmethod
    def _validation_schema() -> JsonSchemaValue:
        """Return the HTTP state schema for validation diagnostics."""
        return TypeAdapter(HaproxyRouteState).json_schema()


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

    path: Optional[Annotated[str, BeforeValidator(value_has_valid_characters)]] = Field(
        json_schema_extra={"sources": {"config": ["health-check-path"]}}
    )
    port: Optional[int] = Field(
        gt=0, le=65536, json_schema_extra={"sources": {"config": ["health-check-port"]}}
    )
    interval: Optional[int] = Field(
        gt=0, json_schema_extra={"sources": {"config": ["health-check-interval"]}}
    )
    rise: Optional[int] = Field(
        gt=0, json_schema_extra={"sources": {"config": ["health-check-rise"]}}
    )
    fall: Optional[int] = Field(
        gt=0, json_schema_extra={"sources": {"config": ["health-check-fall"]}}
    )

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


# pylint: disable=too-many-instance-attributes,too-many-locals
@dataclass(
    frozen=True,
    config=ConfigDict(
        json_schema_extra={
            "sources": {"config": ["external-grpc-port", "backend-protocol", "allow-http"]},
        }
    ),
)
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
        deny_paths: List of URL paths that should not be routed to the service.
        hostname: The hostname to route to the service.
        additional_hostnames: List of additional hostnames to route to the service.
        load_balancing_configuration: Load balancing configuration.
        http_server_close: Configure server close after request.
        path_rewrite_expressions: List of path rewrite expressions.
        header_rewrite_expressions: List of header rewrite expressions.
        allow_http: Whether to allow HTTP traffic to the service.
        external_grpc_port: Optional gRPC external port.
    """

    backend_addresses: Annotated[
        list[IPvAnyAddress], Len(min_length=1), BeforeValidator(split_delimited)
    ] = Field(
        json_schema_extra={
            "sources": {
                "config": ["backend-addresses"],
                "ingress": ["ip"],
                "Kubernetes Node": ["status.addresses"],
            }
        }
    )
    backend_ports: Annotated[
        list[Annotated[int, Field(gt=0, le=65535)]],
        Len(min_length=1),
        BeforeValidator(split_delimited),
    ] = Field(
        json_schema_extra={
            "sources": {
                "config": ["backend-ports"],
                "ingress": ["port"],
                "Kubernetes Service": ["nodePort"],
            }
        }
    )
    backend_protocol: Literal["http", "https"] = Field(
        json_schema_extra={"sources": {"config": ["backend-protocol"]}}
    )
    health_check: HealthCheck = Field(
        json_schema_extra={
            "sources": {
                "config": ["health-check-interval", "health-check-rise", "health-check-fall"]
            }
        }
    )
    retry: Retry | None = Field(
        json_schema_extra={
            "sources": {"config": ["retry-count", "retry-redispatch"]},
            "properties": {
                "count": {"sources": {"config": ["retry-count"]}},
                "redispatch": {"sources": {"config": ["retry-redispatch"]}},
            },
        }
    )
    timeout: TimeoutConfiguration = Field(
        json_schema_extra={
            "sources": {"config": ["timeout-server", "timeout-connect", "timeout-queue"]},
            "properties": {
                "server": {"sources": {"config": ["timeout-server"]}},
                "connect": {"sources": {"config": ["timeout-connect"]}},
                "queue": {"sources": {"config": ["timeout-queue"]}},
            },
        }
    )
    service: str = Field(
        ...,
        min_length=1,
        json_schema_extra={
            "sources": {
                "Juju": ["model/application name"],
                "Kubernetes Service": ["metadata.name"],
            }
        },
    )
    paths: Annotated[
        list[Annotated[str, BeforeValidator(value_has_valid_characters)]],
        BeforeValidator(split_delimited),
    ] = Field(default=[], json_schema_extra={"sources": {"config": ["paths"]}})
    deny_paths: Annotated[
        list[Annotated[str, BeforeValidator(value_has_valid_characters)]],
        BeforeValidator(split_delimited),
    ] = Field(default=[], json_schema_extra={"sources": {"config": ["deny-paths"]}})
    hostname: Optional[Annotated[str, BeforeValidator(valid_domain_with_wildcard)]] = Field(
        default=None, json_schema_extra={"sources": {"config": ["hostname"]}}
    )
    additional_hostnames: Annotated[
        list[Annotated[str, BeforeValidator(valid_domain_with_wildcard)]],
        BeforeValidator(split_delimited),
    ] = Field(default=[], json_schema_extra={"sources": {"config": ["additional-hostnames"]}})
    load_balancing_configuration: LoadBalancingConfiguration = Field(
        default=LoadBalancingConfiguration(),
        json_schema_extra={
            "sources": {
                "config": [
                    "load-balancing-algorithm",
                    "load-balancing-cookie",
                    "load-balancing-consistent-hashing",
                ]
            },
            "properties": {
                "algorithm": {"sources": {"config": ["load-balancing-algorithm"]}},
                "cookie": {"sources": {"config": ["load-balancing-cookie"]}},
                "consistent_hashing": {
                    "sources": {"config": ["load-balancing-consistent-hashing"]}
                },
            },
        },
    )
    http_server_close: bool = Field(
        default=False, json_schema_extra={"sources": {"config": ["http-server-close"]}}
    )
    path_rewrite_expressions: list[str] = Field(
        default=[], json_schema_extra={"sources": {"config": ["path-rewrite-expressions"]}}
    )
    header_rewrite_expressions: list[tuple[str, str]] = Field(
        default=[], json_schema_extra={"sources": {"config": ["header-rewrite-expressions"]}}
    )
    allow_http: bool = Field(
        default=False, json_schema_extra={"sources": {"config": ["allow-http"]}}
    )
    external_grpc_port: int | None = Field(
        default=None,
        gt=0,
        le=65535,
        json_schema_extra={"sources": {"config": ["external-grpc-port"]}},
    )

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

    @staticmethod
    def has_integrator_config(charm: ops.CharmBase) -> bool:
        """Return True if any integrator backend config option is set.

        This is intentionally a presence check — it does not validate the values.
        Use it to detect ambiguous mode (ingress relation + backend config both
        present) before attempting to parse the config with build_for_integrator_mode.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            True if backend-addresses, backend-ports is set in config.
        """
        return bool(charm.config.get("backend-addresses") or charm.config.get("backend-ports"))

    @classmethod
    def build_for_integrator_mode(cls, charm: ops.CharmBase) -> Self:
        """Create HaproxyRouteState for integrator mode from charm config.

        Args:
            charm: the ingress-configurator charm.

        Raises:
            InvalidHaproxyRouteStateError: when the configuration is missing or invalid.

        Returns:
            HaproxyRouteState: instance of the state.
        """
        return cls._build(
            charm,
            cast(str | None, charm.config.get("backend-addresses")),
            cast(str | None, charm.config.get("backend-ports")),
            f"{charm.model.name}-{charm.app.name}",
        )

    @classmethod
    def build_for_adapter_mode(
        cls,
        charm: ops.CharmBase,
        ingress_data: IngressRequirerData,
    ) -> Self:
        """Create HaproxyRouteState for adapter mode from ingress requirer data.

        Args:
            charm: the ingress-configurator charm.
            ingress_data: the ingress requirer relation data.

        Raises:
            InvalidHaproxyRouteStateError: when the configuration is missing or invalid.

        Returns:
            HaproxyRouteState: instance of the state.
        """
        try:
            backend_addresses = [cast(IPvAnyAddress, unit.ip) for unit in ingress_data.units]
            backend_ports = [ingress_data.app.port]
        except ValueError as exc:
            raise InvalidHaproxyRouteStateError(
                "HAProxy route state contains invalid value(s)."
            ) from exc
        return cls._build(
            charm, backend_addresses, backend_ports, f"{charm.model.name}-{charm.app.name}"
        )

    @classmethod
    def build_for_kubernetes_adapter_mode(
        cls,
        charm: ops.CharmBase,
        kubernetes_data: NodePortState,
    ) -> Self:
        """Create HaproxyRouteState from pre-resolved Kubernetes NodePort data.

        Args:
            charm: the ingress-configurator charm.
            kubernetes_data: resolved NodePort service data.

        Raises:
            InvalidHaproxyRouteStateError: when the configuration is invalid.

        Returns:
            HaproxyRouteState: instance of the state.
        """
        return cls._build(
            charm,
            kubernetes_data.backend_addresses,
            [kubernetes_data.backend_port],
            kubernetes_data.service_name,
        )

    @classmethod
    def _build(
        cls,
        charm: ops.CharmBase,
        backend_addresses: list[IPvAnyAddress] | str | None,
        backend_ports: list[int] | str | None,
        service: str,
    ) -> Self:
        """Build HaproxyRouteState from resolved backend fields and charm config.

        Args:
            charm: the ingress-configurator charm.
            backend_addresses: Resolved IP addresses or raw comma-separated config.
            backend_ports: Resolved ports or raw comma-separated config.
            service: the service name.

        Raises:
            InvalidHaproxyRouteStateError: when the configuration is invalid.

        Returns:
            HaproxyRouteState: instance of the state.
        """
        try:
            external_grpc_port = cast(int | None, charm.config.get("external-grpc-port"))
            hostname = cast(Optional[str], charm.config.get("hostname"))
            http_server_close = cast(bool, charm.config.get("http-server-close", False))
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
                {
                    "count": retry_count,
                    "redispatch": charm.config.get("retry-redispatch"),
                }
                if retry_count is not None
                else None
            )
            timeout = {
                k: v
                for k, v in {
                    "server": charm.config.get("timeout-server"),
                    "connect": charm.config.get("timeout-connect"),
                    "queue": charm.config.get("timeout-queue"),
                }.items()
                if v is not None
            }
            allow_http = cast(bool, charm.config.get("allow-http", False))
            backend_protocol = cast(
                Literal["http", "https"],
                charm.config.get("backend-protocol", "http"),
            )
            return TypeAdapter(cls).validate_python(
                {
                    "backend_addresses": backend_addresses,
                    "backend_ports": backend_ports,
                    "backend_protocol": backend_protocol,
                    "paths": charm.config.get("paths"),
                    "deny_paths": charm.config.get("deny-paths"),
                    "health_check": {
                        "interval": charm.config.get("health-check-interval"),
                        "rise": charm.config.get("health-check-rise"),
                        "fall": charm.config.get("health-check-fall"),
                        "path": charm.config.get("health-check-path"),
                        "port": charm.config.get("health-check-port"),
                    },
                    "retry": retry,
                    "timeout": timeout,
                    "service": service,
                    "hostname": hostname,
                    "additional_hostnames": charm.config.get("additional-hostnames"),
                    "load_balancing_configuration": {
                        "algorithm": charm.config.get(
                            "load-balancing-algorithm", LoadBalancingAlgorithm.LEASTCONN.value
                        ),
                        "cookie": charm.config.get("load-balancing-cookie"),
                        "consistent_hashing": charm.config.get(
                            "load-balancing-consistent-hashing", False
                        ),
                    },
                    "http_server_close": http_server_close,
                    "path_rewrite_expressions": path_rewrite_expressions,
                    "header_rewrite_expressions": header_rewrite_expressions,
                    "allow_http": allow_http,
                    "external_grpc_port": external_grpc_port,
                }
            )
        except ValidationError as exc:
            raise InvalidHaproxyRouteStateError(
                "Invalid haproxy-route configuration",
                validation_error=exc,
            ) from exc
