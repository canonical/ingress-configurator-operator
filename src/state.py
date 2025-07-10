# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import logging
import typing
from enum import Enum

import ops
from pydantic import Field, ValidationError
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","


class Mode(Enum):
    """Enum representing the mode of the charm.

    Attrs:
        INTEGRATOR: integrator mode.
        ADAPTER: afapter mode.
    """

    INTEGRATOR = "integrator"
    ADAPTER = "adapter"


class UndefinedModeError(Exception):
    """Exception raised when the charm is in an undefined state."""


def get_mode(charm: ops.CharmBase, ingress_relation: ops.Relation | None) -> Mode:
    """Detect the operation mode of the charm.

    Args:
        charm: the charm.
        ingress_relation: the ingress relation.

    Returns:
        The operation mode of the charm, either "integrator" or "adapter".

    Raises:
        UndefinedModeError: When we cannot detect the operation mode.
    """
    if (
        charm.config.get("backend-addresses") or charm.config.get("backend-ports")
    ) and ingress_relation:
        raise UndefinedModeError("Both integrator and adapter configurations are set.")
    if charm.config.get("backend-addresses") and charm.config.get("backend-ports"):
        return Mode.INTEGRATOR
    if ingress_relation:
        return Mode.ADAPTER
    raise UndefinedModeError("No valid mode detected.")


class InvalidIntegratorConfigError(Exception):
    """Exception raised when a configuration in integrator mode is invalid."""


@dataclass(frozen=True)
class IntegratorInformation:
    """A component of charm state that contains the configuration in integrator mode.

    Attributes:
        backend_addresses: Configured list of backend ip addresses in integrator mode.
        backend_ports: Configured list of backend ports in integrator mode.
        retry_count: Number of times to retry failed requests.
        retry_interval: Interval between retries in seconds.
        retry_redispatch: Whether to redispatch failed requests to another server.
    """

    backend_addresses: list[IPvAnyAddress] = Field(
        description="Configured list of backend ip addresses in integrator mode."
    )
    backend_ports: list[typing.Annotated[int, Field(gt=0, le=65535)]] = Field(
        description="Configured list of backend ports in integrator mode."
    )
    retry_count: int | None = Field(gt=0)
    retry_interval: int | None = Field(gt=0)
    retry_redispatch: bool | None = False

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
        backend_addresses = (
            [
                typing.cast(IPvAnyAddress, address)
                for address in typing.cast(str, charm.config.get("backend-addresses")).split(",")
            ]
            if charm.config.get("backend-addresses")
            else []
        )
        backend_ports = (
            [int(port) for port in typing.cast(str, charm.config.get("backend-ports")).split(",")]
            if charm.config.get("backend-ports")
            else []
        )
        retry_count = (
            typing.cast(int, charm.config.get("retry-count"))
            if charm.config.get("retry-count")
            else None
        )
        retry_interval = (
            typing.cast(int, charm.config.get("retry-interval"))
            if charm.config.get("retry-interval")
            else None
        )
        retry_redispatch = (
            typing.cast(bool, charm.config.get("retry-redispatch"))
            if charm.config.get("retry-redispatch")
            else None
        )
        try:
            return cls(
                backend_addresses=backend_addresses,
                backend_ports=backend_ports,
                retry_count=retry_count,
                retry_interval=retry_interval,
                retry_redispatch=retry_redispatch,
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
