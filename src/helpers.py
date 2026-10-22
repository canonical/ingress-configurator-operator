# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods to validate the charm state."""

import hashlib
import logging
import string

from pydantic import ValidationError

logger = logging.getLogger()

_K8S_RESOURCE_NAME_MAX_LENGTH = 63


def truncate_k8s_resource_name(name: str) -> str:
    """Truncate a Kubernetes resource name to fit within the 63-character limit.

    If the name exceeds 63 characters, it is truncated and a short hash suffix
    is appended to ensure uniqueness. The resulting name is at most 63
    characters long.

    Args:
        name: The desired resource name.

    Returns:
        The name, possibly truncated with a hash suffix appended.
    """
    if len(name) <= _K8S_RESOURCE_NAME_MAX_LENGTH:
        return name
    # Use an 8-char hex digest for collision avoidance. usedforsecurity=False
    # marks this as a non-security use, which also allows MD5 in FIPS environments.
    suffix = hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:8]
    # Truncate the name leaving room for a dash and the 8-char suffix.
    max_prefix_length = _K8S_RESOURCE_NAME_MAX_LENGTH - len(suffix) - 1
    truncated = name[:max_prefix_length].rstrip("-")
    return f"{truncated}-{suffix}"


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


def format_validation_error(exc: ValidationError) -> str:
    """Format Pydantic validation reasons and locations for diagnostic logs.

    Preserve model names, nested paths, and model-level errors. Omit Pydantic's
    input and documentation URL metadata, but retain validator messages as-is.

    Args:
        exc: The validation error exception.

    Returns:
        The model name and semicolon-separated validation locations and reasons.
    """
    details = []
    for error in exc.errors(include_url=False, include_input=False, include_context=False):
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}" if location else error["msg"])
    return f"{exc.title}: {'; '.join(details)}"


class InvalidRouteStateError(Exception):
    """Invalid route state with a concise status and complete diagnostic details.

    Attributes:
        details: The full route state error explanation for logging.
    """

    def __init__(self, message: str, *, validation_error: ValueError | None = None) -> None:
        """Initialize the status summary and diagnostic details.

        Args:
            message: User-facing route state error summary. Used unchanged when no
                validation error is supplied; otherwise followed by a debug-log hint.
            validation_error: The original validation or parsing error, if any.
        """
        if validation_error is None:
            self.details = message
            self._status_message = message
        else:
            reason = (
                format_validation_error(validation_error)
                if isinstance(validation_error, ValidationError)
                else str(validation_error)
            )
            self.details = f"{message}: {reason}"
            self._status_message = f"{message}; see debug-log"
        self._error_count = (
            validation_error.error_count() if isinstance(validation_error, ValidationError) else 0
        )
        super().__init__(self.details)

    def __str__(self) -> str:
        """Return the status summary, including the count for multiple errors.

        Counts come from the supplied Pydantic validation call, not from distinct
        fields or subsequent validation calls.
        """
        if self._error_count > 1:
            return f"{self._error_count} validation errors; see debug-log"
        return self._status_message


def split_delimited(value: object, *, delimiter: str = ",") -> object:
    """Split trimmed nonempty string items; preserve already-parsed inputs.

    Args:
        value: A delimited string, unset value, or already-parsed field input.
        delimiter: Separator between items, defaulting to a comma.

    Returns:
        Trimmed nonempty items for strings, an empty list for None, or the original value.

    Raises:
        ValueError: If a string input is split with an empty delimiter.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(delimiter) if item.strip()]
    return value
