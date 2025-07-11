# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for the state module."""

import logging
import re
import string

from pydantic import ValidationError

logger = logging.getLogger()

PATH_REGEX = re.compile(r"^(/[a-zA-Z0-9\-_\.]*)*$")


def validate_path(path: str) -> str:
    """Validate a URL path.

    Args:
        path: The URL path to validate.

    Raises:
        ValueError: If the path is invalid.

    Returns:
        path: The validated path.
    """
    if not PATH_REGEX.fullmatch(path):
        raise ValueError(f"Invalid path format: {path}")

    if ".." in path:
        raise ValueError("Path must not contain '..'")

    if "//" in path:
        raise ValueError("Path must not contain '//'")

    if len(path) > 2048:
        raise ValueError("Path is too long (max 2048 characters)")

    return path


def validate_subdomain(subdomain: str) -> str:
    """Validate a subdomain.

    Args:
        subdomain: The subdomain to validate.

    Raises:
        ValueError: If the subdomain is invalid.

    Returns:
        subdomain: The validated subdomain.
    """
    if len(subdomain) > 253:
        raise ValueError("Subdomain is too long (max 253 characters)")

    labels = subdomain.split(".")
    allowed_chars = set(string.ascii_letters + string.digits + "-")

    for label in labels:
        if not label:
            raise ValueError(
                "Subdomain contains an empty label. Check for leading/trailing/consecutive dots."
            )

        if not 1 <= len(label) <= 63:
            raise ValueError(f"Label '{label}' must be between 1 and 63 characters")

        if not label[0].isalnum() or not label[-1].isalnum():
            raise ValueError(f"Label '{label}' must start and end with a letter or digit")

        if not all(char in allowed_chars for char in label):
            raise ValueError(f"Label '{label}' contains invalid characters")

    return subdomain


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
