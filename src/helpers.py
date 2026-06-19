# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods to validate the charm state."""

import logging
import string

from pydantic import ValidationError

logger = logging.getLogger()


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
    """Return the top-level field names that failed pydantic validation.

    Only the first element of each error's ``loc`` tuple is kept, so nested
    type paths (e.g. for list items) are collapsed to their parent field.
    Results are de-duplicated while preserving order.

    Args:
        exc: The validation error exception.

    Returns:
        list[str]: De-duplicated top-level field names that failed validation.
    """
    error_fields: list[str] = []
    for error in exc.errors():
        if not error["loc"]:
            continue
        field = str(error["loc"][0])
        if field not in error_fields:
            error_fields.append(field)
    return error_fields
