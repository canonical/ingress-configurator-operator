# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

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
        backend_addresses: Configured list of backend ip addresses in integrator mode.
        backend_ports: Configured list of backend ports in integrator mode.
    """

    backend_addresses: list[IPvAnyAddress] = Field(
        description="Configured list of backend ip addresses in integrator mode."
    )
    backend_ports: list[typing.Annotated[int, Field(gt=0, le=65535)]] = Field(
        description="Configured list of backend ports in integrator mode."
    )

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
        backend_addresses = typing.cast(str, charm.config.get("backend-addresses"))
        backend_ports = typing.cast(str, charm.config.get("backend-ports"))
        if not backend_addresses or not backend_ports:
            raise InvalidIntegratorConfigError(
                (
                    "Missing configuration for integrator mode: "
                    f'{"backend-addresses " if not backend_addresses else ""}'
                    f'{"backend-ports" if not backend_ports else ""}'
                )
            )
        try:
            return cls(
                backend_addresses=[
                    typing.cast(IPvAnyAddress, address) for address in backend_addresses.split(",")
                ],
                backend_ports=[int(port) for port in backend_ports.split(",")],
            )
        except ValidationError as exc:
            logger.error(str(exc))
            error_field_str = ",".join(f"{field}" for field in get_invalid_config_fields(exc))
            raise InvalidIntegratorConfigError(
                f"Invalid integrator configuration: {error_field_str}"
            ) from exc
        except ValueError as exc:
            logger.error(str(exc))
            raise InvalidIntegratorConfigError(
                f"Configured backend-ports contains invalid value(s): {backend_ports}."
            ) from exc


def get_invalid_config_fields(exc: ValidationError) -> list[str]:
    """Return a list on invalid config from pydantic validation error.

    Args:
        exc: The validation error exception.

    Returns:
        str: list of fields that failed validation.
    """
    logger.info(exc.errors())
    error_fields = ["-".join([str(i) for i in error["loc"]]) for error in exc.errors()]
    return error_fields
