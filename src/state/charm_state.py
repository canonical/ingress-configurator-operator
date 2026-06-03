# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

from typing import Self, cast

import ops
from pydantic import Field
from pydantic.dataclasses import dataclass


class InvalidStateError(Exception):
    """Exception raised when the state is invalid."""


@dataclass(frozen=True)
class Retry:
    """Charm state that contains the retry configuration.

    Attributes:
        count: Number of times to retry failed requests.
        redispatch: Whether to redispatch failed requests to another server.
    """

    count: int | None = Field(gt=0)
    redispatch: bool | None = None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase, prefix: str = "") -> Self:
        """Create an Retry class from a charm instance.

        Args:
            charm: the ingress-configurator charm.
            prefix: prefix for the configuration option.

        Returns:
            Retry: instance of the retry component.
        """
        return cls(
            count=cast(int | None, charm.config.get(f"{prefix}retry-count")),
            redispatch=cast(bool | None, charm.config.get(f"{prefix}retry-redispatch")),
        )


@dataclass(frozen=True)
class Timeout:
    """Backend timeout configuration.

    Attributes:
        server: Server timeout in seconds.
        connect: Connect timeout in seconds.
        queue: Queue timeout in seconds.
    """

    server: int | None = Field(default=None, gt=0)
    connect: int | None = Field(default=None, gt=0)
    queue: int | None = Field(default=None, gt=0)

    @classmethod
    def from_charm(cls, charm: ops.CharmBase, prefix: str = "") -> Self:
        """Create a Timeout from charm config.

        Args:
            charm: The charm instance.
            prefix: prefix for the configuration option.

        Returns:
            Timeout instance.
        """
        return cls(
            server=cast(int | None, charm.config.get(f"{prefix}timeout-server")),
            connect=cast(int | None, charm.config.get(f"{prefix}timeout-connect")),
            queue=cast(int | None, charm.config.get(f"{prefix}timeout-queue")),
        )
