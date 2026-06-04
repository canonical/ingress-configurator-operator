# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""HAProxy TCP route state management module.

This module provides state management functionality for HAProxy TCP routes
in the ingress configurator operator.
"""

import logging
from typing import Annotated, Optional, Self, cast

import ops
from annotated_types import Len
from charms.haproxy.v1.haproxy_route_tcp import (
    LoadBalancingAlgorithm,
    Retry,
    TCPHealthCheckType,
    TCPLoadBalancingConfiguration,
    TimeoutConfiguration,
    valid_domain_with_wildcard,
)
from pydantic import BeforeValidator, Field, ValidationError, model_validator
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from helpers import get_invalid_config_fields

logger = logging.getLogger(__name__)


class InvalidHaproxyRouteTcpStateError(Exception):
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

    interval: Optional[int] = Field(default=None, gt=0)
    rise: Optional[int] = Field(default=None, gt=0)
    fall: Optional[int] = Field(default=None, gt=0)
    check_type: Optional[TCPHealthCheckType] = None
    send: Optional[str] = None
    expect: Optional[str] = None
    db_user: Optional[str] = None

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

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> Self:
        """Create a TCPHealthCheck from charm config.

        Args:
            charm: The charm instance.

        Raises:
            InvalidStateError: If the health check type is invalid.

        Returns:
            TCPHealthCheck instance.
        """
        check_type_str = cast(Optional[str], charm.config.get("tcp-health-check-type"))
        check_type = None
        if check_type_str:
            try:
                check_type = TCPHealthCheckType(check_type_str)
            except ValueError as exc:
                raise InvalidHaproxyRouteTcpStateError(
                    f"Invalid health check type: {check_type_str}. "
                    "Must be one of: generic, mysql, postgres, redis, smtp."
                ) from exc

        return cls(
            interval=cast(Optional[int], charm.config.get("tcp-health-check-interval")),
            rise=cast(Optional[int], charm.config.get("tcp-health-check-rise")),
            fall=cast(Optional[int], charm.config.get("tcp-health-check-fall")),
            check_type=check_type,
            send=cast(Optional[str], charm.config.get("tcp-health-check-send")),
            expect=cast(Optional[str], charm.config.get("tcp-health-check-expect")),
            db_user=cast(Optional[str], charm.config.get("tcp-health-check-db-user")),
        )


@dataclass(frozen=True)
class HaproxyRouteTcpState:  # pylint: disable=too-many-instance-attributes
    """Requirements for HAProxy TCP route configuration.

    Defines the necessary parameters and constraints for establishing
    TCP routes through HAProxy.

    Raises:
        InvalidHaproxyRouteTcpRequirementsError: If the provided configuration
            parameters are invalid.

    Attributes:
        backend_addresses: List of backend IP addresses.
        port: Frontend port for the TCP route.
        backend_port: Backend port for the TCP route.
        tls_terminate: Whether to enable TLS termination.
        hostname: Optional hostname for SNI (Server Name Indication).
        retry: Retry configuration.
        load_balancing_configuration: TCP load balancing configuration.
        enforce_tls: Whether to enforce TLS for all TCP traffic.
        health_check: TCP health check configuration.
        proxy_protocol: Whether to enable PROXY protocol when connecting to backend servers.
    """

    backend_addresses: Annotated[list[IPvAnyAddress], Len(min_length=1)]
    backend_port: Annotated[int, Field(gt=0, le=65535)]
    port: Annotated[int, Field(gt=0, le=65535)]
    tls_terminate: bool
    hostname: Annotated[str, BeforeValidator(valid_domain_with_wildcard)] | None
    retry: Retry | None
    load_balancing_configuration: TCPLoadBalancingConfiguration
    enforce_tls: bool
    health_check: TCPHealthCheck
    timeout: TimeoutConfiguration
    proxy_protocol: bool

    @classmethod
    def has_integrator_config(cls, charm: ops.CharmBase) -> bool:
        """Return True if any TCP integrator backend config option is set.

        This is intentionally a presence check — it does not validate the values.
        Use it to detect the absence of backend configuration before attempting
        to parse the config with for_integrator_mode.

        Args:
            charm: the ingress-configurator charm.

        Returns:
            True if tcp-backend-addresses or tcp-backend-port is set in config.
        """
        return any(
            [
                charm.config.get("tcp-backend-addresses"),
                charm.config.get("tcp-backend-port"),
            ]
        )

    @classmethod
    def for_integrator_mode(cls, charm: ops.CharmBase) -> Self:
        """Create HaproxyRouteTcpState for integrator mode from charm config.

        Args:
            charm: the ingress-configurator charm.

        Raises:
            InvalidHaproxyRouteTcpStateError: when backend config is missing or invalid.

        Returns:
            HaproxyRouteTcpState: instance of the TCP state.
        """
        try:
            backend_addresses = (
                [
                    cast(IPvAnyAddress, address)
                    for address in cast(str, charm.config.get("tcp-backend-addresses")).split(",")
                ]
                if charm.config.get("tcp-backend-addresses")
                else []
            )
            backend_port = cast(int, charm.config.get("tcp-backend-port"))
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidHaproxyRouteTcpStateError(
                "TCP backend state contains invalid value(s)."
            ) from exc
        return cls._build(charm, backend_addresses, backend_port)

    @classmethod
    def _build(
        cls,
        charm: ops.CharmBase,
        backend_addresses: list[IPvAnyAddress],
        backend_port: int,
    ) -> Self:
        """Build HaproxyRouteTcpState from resolved backend fields and charm config.

        Args:
            charm: The IngressConfiguratorCharm instance.
            backend_addresses: list of resolved backend IP addresses.
            backend_port: the resolved backend port.

        Raises:
            InvalidHaproxyRouteTcpStateError: If the configuration
                parameters are invalid.

        Returns:
            HaproxyRouteTcpState instance populated with relevant info.
        """
        tls_terminate = cast(bool, charm.config.get("tcp-tls-terminate", True))
        port = cast(int, charm.config.get("tcp-frontend-port"))
        hostname = cast(str | None, charm.config.get("tcp-hostname"))
        enforce_tls = cast(bool, charm.config.get("tcp-enforce-tls"))
        try:
            load_balancing_algorithm = LoadBalancingAlgorithm(
                cast(str, charm.config.get("tcp-load-balancing-algorithm"))
            )
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidHaproxyRouteTcpStateError("Invalid load balancing algorithm.") from exc

        try:
            load_balancing_configuration = TCPLoadBalancingConfiguration(
                algorithm=load_balancing_algorithm,
                consistent_hashing=cast(
                    bool, charm.config.get("tcp-load-balancing-consistent-hashing")
                ),
            )
            retry_count = cast(int | None, charm.config.get("tcp-retry-count"))
            retry = (
                Retry(
                    count=retry_count,
                    redispatch=cast(bool, charm.config.get("tcp-retry-redispatch")),
                )
                if retry_count is not None
                else None
            )
            return cls(
                backend_addresses=backend_addresses,
                backend_port=backend_port,
                port=port,
                tls_terminate=tls_terminate,
                hostname=hostname,
                retry=retry,
                load_balancing_configuration=load_balancing_configuration,
                enforce_tls=enforce_tls,
                health_check=TCPHealthCheck.from_charm(charm),
                timeout=TimeoutConfiguration(
                    server=cast(int | None, charm.config.get("tcp-timeout-server")),
                    connect=cast(int | None, charm.config.get("tcp-timeout-connect")),
                    queue=cast(int | None, charm.config.get("tcp-timeout-queue")),
                ),
                proxy_protocol=cast(bool, charm.config.get("tcp-enable-proxy-protocol", False)),
            )
        except ValidationError as exc:
            logger.error(
                "Failed to validate haproxy-route-tcp requirements. Invalid config fields: %s",
                get_invalid_config_fields(exc),
            )
            raise InvalidHaproxyRouteTcpStateError(
                "Invalid haproxy-route-tcp configuration."
            ) from exc
