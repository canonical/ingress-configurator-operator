# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""HAProxy TCP route state management module.

This module provides state management functionality for HAProxy TCP routes
in the ingress configurator operator.
"""

import logging
from typing import Annotated, cast

import ops
from annotated_types import Len
from charms.haproxy.v0.haproxy_route_tcp import (
    LoadBalancingAlgorithm,
    TCPLoadBalancingConfiguration,
)
from pydantic import Field, ValidationError
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

from state.charm_state import Retry
from validators import get_invalid_config_fields

logger = logging.getLogger(__name__)


class InvalidHaproxyRouteTcpRequirementsError(Exception):
    """Exception raised when HaproxyRouteTcpRequirements contains invalid attributes."""


@dataclass(frozen=True)
class HaproxyRouteTcpRequirements:
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
    """

    backend_addresses: Annotated[list[IPvAnyAddress], Len(min_length=1)]
    port: Annotated[int, Field(gt=0, le=65535)]
    backend_port: Annotated[int, Field(gt=0, le=65535)]
    tls_terminate: bool
    hostname: str | None
    retry: Retry
    load_balancing_configuration: TCPLoadBalancingConfiguration
    enforce_tls: bool

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "HaproxyRouteTcpRequirements":
        """Create HaproxyRouteTcpRequirements from charm and requirer.

        Args:
            charm: The IngressConfiguratorCharm instance.

        Raises:
            InvalidHaproxyRouteTcpRequirementsError: If the configuration
                parameters are invalid.

        Returns:
            HaproxyRouteTcpRequirements instance populated with relevant info.
        """
        config_tcp_backend_addresses = (
            [
                cast(IPvAnyAddress, address)
                for address in cast(str, charm.config.get("tcp-backend-addresses")).split(",")
            ]
            if charm.config.get("tcp-backend-addresses")
            else []
        )
        tls_terminate = cast(bool, charm.config.get("tcp-tls-terminate", True))
        port = cast(int, charm.config.get("tcp-frontend-port"))
        backend_port = cast(int, charm.config.get("tcp-backend-port"))
        hostname = cast(str | None, charm.config.get("tcp-hostname"))
        enforce_tls = cast(bool, charm.config.get("tcp-enforce-tls", True))
        try:
            load_balancing_algorithm = LoadBalancingAlgorithm(
                cast(str, charm.config.get("tcp-load-balancing-algorithm"))
            )
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidHaproxyRouteTcpRequirementsError(
                "Invalid load balancing algorithm."
            ) from exc

        try:
            load_balancing_configuration = TCPLoadBalancingConfiguration(
                algorithm=load_balancing_algorithm,
                consistent_hashing=cast(
                    bool, charm.config.get("tcp-load-balancing-consistent-hashing")
                ),
            )
            return cls(
                port=port,
                backend_port=backend_port,
                tls_terminate=tls_terminate,
                hostname=hostname,
                backend_addresses=config_tcp_backend_addresses,
                retry=Retry.from_charm(charm, prefix="tcp-"),
                load_balancing_configuration=load_balancing_configuration,
                enforce_tls=enforce_tls,
            )
        except ValidationError as exc:
            logger.error(
                "Failed to validate haproxy-route-tcp requirements. Invalid config fields: %s",
                get_invalid_config_fields(exc),
            )
            raise InvalidHaproxyRouteTcpRequirementsError(
                "Invalid haproxy-route-tcp configuration."
            ) from exc
