# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""HAProxy TCP route state management module.

This module provides state management functionality for HAProxy TCP routes
in the ingress configurator operator.
"""

from typing import Annotated, Optional, Self, cast

import ops
from annotated_types import Len
from charms.haproxy.v1.haproxy_route_tcp import (
    PortMapping,
    Retry,
    TCPHealthCheckType,
    TCPLoadBalancingConfiguration,
    TimeoutConfiguration,
    valid_domain_with_wildcard,
)
from pydantic import (
    BeforeValidator,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from helpers import InvalidRouteStateError, split_delimited


class InvalidHaproxyRouteTcpStateError(InvalidRouteStateError):
    """Exception raised when HAProxy TCP route requirements are invalid."""


@dataclass(frozen=True)
class TCPHealthCheck:
    """TCP health check configuration.

    Attributes:
        interval: Interval between health checks in seconds.
        rise: Number of successful health checks before server is considered up.
        fall: Number of failed health checks before server is considered down.
        check_type: Health check type (generic, mysql, postgres, redis, smtp).
        send: String to send in health check request (generic type only).
        expect: Expected response string (generic type only).
        db_user: Database user for health checks (mysql/postgres types only).
    """

    interval: Optional[int] = Field(
        default=None,
        gt=0,
        json_schema_extra={"sources": {"config": ["tcp-health-check-interval"]}},
    )
    rise: Optional[int] = Field(
        default=None, gt=0, json_schema_extra={"sources": {"config": ["tcp-health-check-rise"]}}
    )
    fall: Optional[int] = Field(
        default=None, gt=0, json_schema_extra={"sources": {"config": ["tcp-health-check-fall"]}}
    )
    check_type: Optional[TCPHealthCheckType] = Field(
        default=None, json_schema_extra={"sources": {"config": ["tcp-health-check-type"]}}
    )
    send: Optional[str] = Field(
        default=None, json_schema_extra={"sources": {"config": ["tcp-health-check-send"]}}
    )
    expect: Optional[str] = Field(
        default=None, json_schema_extra={"sources": {"config": ["tcp-health-check-expect"]}}
    )
    db_user: Optional[str] = Field(
        default=None, json_schema_extra={"sources": {"config": ["tcp-health-check-db-user"]}}
    )

    @model_validator(mode="after")
    def validate_health_check_all_set(self) -> Self:
        """Validate that all health check fields are set together.

        Returns:
            This class instance.

        Raises:
            ValueError: If only some health check fields are set.
        """
        all_or_none_health_checks_set = (
            (self.interval is None) == (self.rise is None) == (self.fall is None)
        )
        if not all_or_none_health_checks_set:
            raise ValueError(
                "Health check configuration is incomplete: interval, rise, and "
                "fall must all be set if any one of them is specified."
            )
        return self


@dataclass(frozen=True)
class HaproxyRouteTcpState:  # pylint: disable=too-many-instance-attributes
    """Requirements for HAProxy TCP route configuration.

    Defines the necessary parameters and constraints for establishing
    TCP routes through HAProxy.

    Raises:
        InvalidHaproxyRouteTcpStateError: If the provided configuration
            parameters are invalid.

    Attributes:
        backend_addresses: List of backend IP addresses.
        port_mapping: Port range mapping from frontend to backend (covers both single-port
            and range modes).
        tls_terminate: Whether to enable TLS termination.
        hostname: Optional hostname for SNI (Server Name Indication).
        retry: Retry configuration.
        load_balancing_configuration: TCP load balancing configuration.
        enforce_tls: Whether to enforce TLS for all TCP traffic.
        health_check: TCP health check configuration.
        proxy_protocol: Whether to enable PROXY protocol when connecting to backend servers.
    """

    backend_addresses: Annotated[
        list[IPvAnyAddress], Len(min_length=1), BeforeValidator(split_delimited)
    ] = Field(json_schema_extra={"sources": {"config": ["tcp-backend-addresses"]}})
    tls_terminate: bool = Field(json_schema_extra={"sources": {"config": ["tcp-tls-terminate"]}})
    hostname: Annotated[str, BeforeValidator(valid_domain_with_wildcard)] | None = Field(
        json_schema_extra={"sources": {"config": ["tcp-hostname"]}}
    )
    retry: Retry | None = Field(
        json_schema_extra={
            "sources": {"config": ["tcp-retry-count", "tcp-retry-redispatch"]},
            "properties": {
                "count": {"sources": {"config": ["tcp-retry-count"]}},
                "redispatch": {"sources": {"config": ["tcp-retry-redispatch"]}},
            },
        }
    )
    load_balancing_configuration: TCPLoadBalancingConfiguration = Field(
        json_schema_extra={
            "sources": {
                "config": [
                    "tcp-load-balancing-algorithm",
                    "tcp-load-balancing-consistent-hashing",
                ]
            },
            "properties": {
                "algorithm": {"sources": {"config": ["tcp-load-balancing-algorithm"]}},
                "consistent_hashing": {
                    "sources": {"config": ["tcp-load-balancing-consistent-hashing"]}
                },
            },
        }
    )
    enforce_tls: bool = Field(json_schema_extra={"sources": {"config": ["tcp-enforce-tls"]}})
    health_check: TCPHealthCheck = Field(
        json_schema_extra={
            "sources": {
                "config": [
                    "tcp-health-check-interval",
                    "tcp-health-check-rise",
                    "tcp-health-check-fall",
                ]
            }
        }
    )
    timeout: TimeoutConfiguration = Field(
        json_schema_extra={
            "sources": {
                "config": ["tcp-timeout-server", "tcp-timeout-connect", "tcp-timeout-queue"]
            },
            "properties": {
                "server": {"sources": {"config": ["tcp-timeout-server"]}},
                "connect": {"sources": {"config": ["tcp-timeout-connect"]}},
                "queue": {"sources": {"config": ["tcp-timeout-queue"]}},
            },
        }
    )
    proxy_protocol: bool = Field(
        json_schema_extra={"sources": {"config": ["tcp-enable-proxy-protocol"]}}
    )
    port_mapping: PortMapping = Field(
        json_schema_extra={
            "sources": {"config": ["tcp-port-mapping", "tcp-frontend-port", "tcp-backend-port"]}
        }
    )

    @field_validator("port_mapping", mode="before")
    @classmethod
    def parse_port_mapping(cls, value: object) -> object:
        """Resolve raw port alternatives and parse mappings, preserving resolved values.

        Args:
            value: Raw port alternatives, a mapping string, or parsed mapping input.

        Returns:
            A parsed mapping for raw input, otherwise the original value.

        Raises:
            ValueError: If port alternatives conflict or a raw mapping string is invalid.
        """
        if isinstance(value, dict) and "mapping" in value:
            mapping = value["mapping"]
            frontend_port = value.get("frontend_port")
            backend_port = value.get("backend_port")
            if mapping is not None and (frontend_port is not None or backend_port is not None):
                raise ValueError(
                    "tcp-port-mapping is mutually exclusive with "
                    "tcp-frontend-port and tcp-backend-port."
                )
            value = mapping if mapping is not None else f"{frontend_port}:{backend_port}"

        if isinstance(value, str):
            return PortMapping.from_string(value.strip())
        return value

    @property
    def port(self) -> int:
        """Return the frontend start port."""
        return self.port_mapping.frontend.start

    @property
    def backend_port(self) -> int:
        """Return the backend start port."""
        return self.port_mapping.backend.start

    @classmethod
    def has_integrator_config(cls, charm: ops.CharmBase) -> bool:
        """Return True if any TCP integrator backend config option is set.

        This is intentionally a presence check — it does not validate the values.
        Use it to detect the absence of backend configuration before attempting
        to parse the config with build_for_integrator_mode.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            True if tcp-backend-addresses or tcp-backend-port or tcp-port-mapping is set in config.
        """
        return bool(
            charm.config.get("tcp-backend-addresses")
            or charm.config.get("tcp-backend-port")
            or charm.config.get("tcp-port-mapping")
        )

    @classmethod
    def build_for_integrator_mode(cls, charm: ops.CharmBase) -> Self:
        """Create HaproxyRouteTcpState for integrator mode from charm config.

        Args:
            charm: the ingress-configurator charm.

        Raises:
            InvalidHaproxyRouteTcpStateError: when backend config is missing or invalid.

        Returns:
            HaproxyRouteTcpState: instance of the TCP state.
        """
        return cls._build(charm, cast(str | None, charm.config.get("tcp-backend-addresses")))

    @classmethod
    def _build(
        cls,
        charm: ops.CharmBase,
        backend_addresses: str | None,
    ) -> Self:
        """Build HaproxyRouteTcpState from backend config and raw port inputs.

        Args:
            charm: The IngressConfiguratorCharm instance.
            backend_addresses: Raw comma-separated backend address config.

        Raises:
            InvalidHaproxyRouteTcpStateError: If the configuration
                parameters are invalid.

        Returns:
            HaproxyRouteTcpState instance populated with relevant info.
        """
        tls_terminate = cast(bool, charm.config.get("tcp-tls-terminate", True))
        hostname = cast(str | None, charm.config.get("tcp-hostname"))
        enforce_tls = cast(bool, charm.config.get("tcp-enforce-tls"))
        try:
            retry_count = cast(int | None, charm.config.get("tcp-retry-count"))
            retry = (
                {
                    "count": retry_count,
                    "redispatch": charm.config.get("tcp-retry-redispatch"),
                }
                if retry_count is not None
                else None
            )
            return TypeAdapter(cls).validate_python(
                {
                    "backend_addresses": backend_addresses,
                    "tls_terminate": tls_terminate,
                    "hostname": hostname,
                    "retry": retry,
                    "load_balancing_configuration": {
                        "algorithm": charm.config.get("tcp-load-balancing-algorithm"),
                        "consistent_hashing": charm.config.get(
                            "tcp-load-balancing-consistent-hashing"
                        ),
                    },
                    "enforce_tls": enforce_tls,
                    "health_check": {
                        "interval": charm.config.get("tcp-health-check-interval"),
                        "rise": charm.config.get("tcp-health-check-rise"),
                        "fall": charm.config.get("tcp-health-check-fall"),
                        "check_type": charm.config.get("tcp-health-check-type") or None,
                        "send": charm.config.get("tcp-health-check-send"),
                        "expect": charm.config.get("tcp-health-check-expect"),
                        "db_user": charm.config.get("tcp-health-check-db-user"),
                    },
                    "timeout": {
                        "server": charm.config.get("tcp-timeout-server"),
                        "connect": charm.config.get("tcp-timeout-connect"),
                        "queue": charm.config.get("tcp-timeout-queue"),
                    },
                    "proxy_protocol": charm.config.get("tcp-enable-proxy-protocol", False),
                    "port_mapping": {
                        "mapping": charm.config.get("tcp-port-mapping"),
                        "frontend_port": charm.config.get("tcp-frontend-port"),
                        "backend_port": charm.config.get("tcp-backend-port"),
                    },
                }
            )
        except ValidationError as exc:
            raise InvalidHaproxyRouteTcpStateError(
                "Invalid haproxy-route-tcp configuration",
                validation_error=exc,
                schema=TypeAdapter(cls).json_schema(),
            ) from exc
