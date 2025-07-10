# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""ingress-configurator-operator integrator information."""

import itertools
import logging
from typing import Annotated, Optional, Set, cast

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


class InvalidIntegratorConfigError(Exception):
    """Exception raised when a configuration in integrator mode is invalid."""


@dataclass(frozen=True)
class IntegratorInformation:
    """A component of charm state that contains the configuration in integrator mode.

    Attributes:
        backend_address: Configured backend ip address in integrator mode.
        backend_port: Configured backend port in integrator mode.
        paths: List of URL paths to route to the service.
        subdomains: List of subdomains to route to the service.
    """

    backend_address: IPvAnyAddress
    backend_port: int = Field(gt=0, le=65535)
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
        backend_address = charm.config.get("backend_address")
        backend_port = charm.config.get("backend_port")
        paths = cast(str, charm.config.get("paths"))
        subdomains = cast(str, charm.config.get("subdomains"))
        if not backend_address or not backend_port:
            raise InvalidIntegratorConfigError(
                (
                    "Missing configuration for integrator mode, "
                    "both backend_port and backend_address must be set."
                )
            )
        try:
            return cls(
                backend_address=cast(IPvAnyAddress, charm.config.get("backend_address")),
                backend_port=cast(int, charm.config.get("backend_port")),
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


def get_invalid_config_fields(exc: ValidationError) -> Set[int | str]:
    """Return a list on invalid config from pydantic validation error.

    Args:
        exc: The validation error exception.

    Returns:
        str: list of fields that failed validation.
    """
    error_fields = set(itertools.chain.from_iterable(error["loc"] for error in exc.errors()))
    return error_fields
