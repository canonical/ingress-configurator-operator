# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import logging
from enum import Enum
from typing import Annotated, Optional, cast

import ops
from pydantic import BeforeValidator, Field, ValidationError
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress

logger = logging.getLogger()
CHARM_CONFIG_DELIMITER = ","
HAPROXY_CONFIG_INVALID_CHARACTERS = "\n\t#\\'\"\r$ "


def value_contains_invalid_characters(value: Optional[str]) -> Optional[str]:
    """Validate if value contains invalid haproxy config characters.

    Args:
        value: The value to validate.

    Raises:
        ValueError: When value contains invalid characters.

    Returns:
        The validated value.
    """
    if value is None:
        return value

    if any(char in value for char in HAPROXY_CONFIG_INVALID_CHARACTERS):
        raise ValueError(f"Relation data contains invalid character(s) {value}")
    return value


VALIDSTR = Annotated[str, BeforeValidator(value_contains_invalid_characters)]


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
    if charm.config.get("backend-addresses") or charm.config.get("backend-ports"):
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
        paths: List of URL paths to route to the service.
        subdomains: List of subdomains to route to the service.
    """

    backend_addresses: list[IPvAnyAddress] = Field(
        description="Configured list of backend ip addresses in integrator mode."
    )
    backend_ports: list[Annotated[int, Field(gt=0, le=65535)]] = Field(
        description="Configured list of backend ports in integrator mode."
    )
    paths: list[VALIDSTR] = Field(default=[])
    subdomains: list[VALIDSTR] = Field(default=[])

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
        backend_addresses = cast(str, charm.config.get("backend-addresses"))
        backend_ports = cast(str, charm.config.get("backend-ports"))
        paths = cast(str, charm.config.get("paths"))
        subdomains = cast(str, charm.config.get("subdomains"))
        if not backend_addresses or not backend_ports:
            raise InvalidIntegratorConfigError(
                "Missing configuration for integrator mode: "
                f'{"backend-addresses " if not backend_addresses else ""}'
                f'{"backend-ports" if not backend_ports else ""}'
            )
        try:
            return cls(
                backend_addresses=[
                    cast(IPvAnyAddress, address) for address in backend_addresses.split(",")
                ],
                backend_ports=[int(port) for port in backend_ports.split(",")],
                paths=(cast(list[str], paths.split(CHARM_CONFIG_DELIMITER)) if paths else []),
                subdomains=(
                    cast(list[str], subdomains.split(CHARM_CONFIG_DELIMITER)) if subdomains else []
                ),
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
