# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import itertools
import logging
import typing

import ops
from pydantic import Field, ValidationError
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","


class InvalidIntegratorConfigError(Exception):
    """Exception raised when a configuration in integrator mode is invalid."""


@dataclass(frozen=True)
class IntegratorInformation:
    """A component of charm state that contains the configuration in integrator mode.

    Attributes:
        backend_address: Configured backend ip address in integrator mode.
        backend_port: Configured backend port in integrator mode.
    """

    backend_address: IPvAnyAddress
    backend_port: int = Field(gt=0, le=65535)

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "IntegratorInformation":
        """Create an IntegratorInformation class from a charm instance.

        Args:
            charm: The ingress-configurator charm.

        Raises:
            InvalidIntegratorConfigError: When the integrator mode config is invalid.

        Returns:
            IntegratorInformation: Instance of the state component.
        """
        backend_address = charm.config.get("backend_address")
        backend_port = charm.config.get("backend_port")
        if not backend_address or not backend_port:
            raise InvalidIntegratorConfigError(
                (
                    "Missing configuration for integrator mode, "
                    "both backend_port and backend_address must be set."
                )
            )
        try:
            return cls(
                backend_address=typing.cast(IPvAnyAddress, charm.config.get("backend_address")),
                backend_port=typing.cast(int, charm.config.get("backend_port")),
            )
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidIntegratorConfigError(
                f"Invalid integrator configuration: {error_field_str}"
            ) from exc


def get_invalid_config_fields(exc: ValidationError) -> typing.Set[int | str]:
    """Return a list on invalid config from pydantic validation error.

    Args:
        exc: The validation error exception.

    Returns:
        str: list of fields that failed validation.
    """
    error_fields = set(itertools.chain.from_iterable(error["loc"] for error in exc.errors()))
    return error_fields
