# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods to validate the charm state."""

import logging
import re
import string

from pydantic import ValidationError

logger = logging.getLogger()

# RFC-1034 and RFC-2181 compliance REGEX for validating FQDNs
# The original regex is complemented to allow an optional port component: (:\d+)?
HOSTNAME_REGEX = (
    r"^(?=.{1,253})(?!.*--.*)(?:(?!-)(?![0-9])[a-zA-Z0-9-]"
    r"{1,63}(?<!-)\.){1,}(?:(?!-)[a-zA-Z0-9-]{1,63}(?<!-))(:\d+)?$"
)

def validate_hostname(value: str) -> str:
    """Validate if value is a valid hostname per RFC 1123.

    Args:
        value: The value to validate.

    Raises:
        ValueError: When value is not a valid hostname.

    Returns:
        The validated value.
    """
    if not re.match(HOSTNAME_REGEX, value):
        raise ValueError(f"Invalid hostname: {value}")
    return value


def value_has_valid_characters(value: str) -> str:
    """Check if a value contains only valid characters.

    Args:
        value: The value to check.

    Returns:
        value: The value if it contains only valid characters.

    Raises:
        ValueError: If the value contains invalid characters.
    """
    valid_characters = string.ascii_letters + string.digits + "-_/."
    if not all(char in valid_characters for char in value):
        raise ValueError(f"Invalid characters in value '{value}'. ")
    return value


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
