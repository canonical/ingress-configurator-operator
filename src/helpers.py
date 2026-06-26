# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods to validate the charm state."""

import hashlib
import logging
import string

from pydantic import ValidationError

logger = logging.getLogger()

_K8S_RESOURCE_NAME_MAX_LENGTH = 63
_GATEWAY_API_SECTION_NAME_MAX_LENGTH = 253


def https_listener_name(gateway_name: str, hostname: str) -> str:
    """Build the per-hostname HTTPS listener name / sectionName.

    The name follows the convention ``{gateway_name}-https-{sanitized_hostname}``
    where dots in the hostname are replaced with hyphens.  The result is capped at
    253 characters (Gateway API SectionName limit).

    This function must produce output **identical** to the equivalent helper in the
    ``gateway-api-integrator`` provider so that the requirer's ``sectionName`` always
    matches the provider's Gateway listener ``name``.

    Args:
        gateway_name: The name of the Gateway K8s resource.
        hostname: The hostname for this listener.

    Returns:
        A listener name of at most 253 characters.
    """
    name = f"{gateway_name}-https-{hostname.replace('.', '-')}"
    return name[:_GATEWAY_API_SECTION_NAME_MAX_LENGTH]


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
