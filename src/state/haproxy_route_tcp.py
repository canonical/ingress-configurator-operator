# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""HAProxy TCP route state management module.

This module provides state management functionality for HAProxy TCP routes
in the ingress configurator operator.
"""

import dataclasses
from typing import Annotated, cast

import ops
from pydantic import Field, IPvAnyAddress


@dataclasses.dataclass
class HaproxyRouteTcpRequirements:
    """Requirements for HAProxy TCP route configuration.

    Defines the necessary parameters and constraints for establishing
    TCP routes through HAProxy.

    Attributes:
        backend_addresses: List of backend IP addresses.
        port: Frontend port for the TCP route.
        backend_port: Backend port for the TCP route.
        tls_terminate: Whether to enable TLS termination.
        hostname: Optional hostname for SNI (Server Name Indication).
    """

    backend_addresses: list[IPvAnyAddress]
    port: Annotated[int, Field(gt=0, le=65535)]
    backend_port: Annotated[int, Field(gt=0, le=65535)]
    tls_terminate: bool
    hostname: str | None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "HaproxyRouteTcpRequirements":
        """Create HaproxyRouteTcpRequirements from charm and requirer.

        Args:
            charm: The IngressConfiguratorCharm instance.

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
        tls_terminate = cast(bool, charm.config.get("tcp-tls-terminate", False))
        port = cast(int, charm.config.get("tcp-frontend-port"))
        backend_port = cast(int, charm.config.get("tcp-backend-port"))
        hostname = cast(str | None, charm.config.get("tcp-hostname"))
        return cls(
            port=port,
            backend_port=backend_port,
            tls_terminate=tls_terminate,
            hostname=hostname,
            backend_addresses=config_tcp_backend_addresses,
        )
