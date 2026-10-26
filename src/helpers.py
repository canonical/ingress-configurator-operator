# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods to validate the charm state."""

import hashlib
import logging
import string

from pydantic import JsonValue, ValidationError
from pydantic.dataclasses import is_pydantic_dataclass

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


class InvalidRouteStateError(Exception):
    """Invalid route state with a concise status and complete diagnostic details.

    Attributes:
        juju_status_msg: Concise message for the unit's Juju status.
        details: The full route state error explanation for logging.
    """

    def __init__(
        self,
        message: str,
        *,
        validation_error: ValidationError,
    ) -> None:
        """Initialize the status summary and diagnostic details.

        Args:
            message: Route state error summary, used in diagnostics.
            validation_error: The original Pydantic validation error.
        """
        self._details = f"{message}: {self._format_validation_error(validation_error)}"
        self._error_count = validation_error.error_count()
        super().__init__(self.details)

    @staticmethod
    def _validation_model() -> type | None:
        """Return the state model associated with this error, if any."""
        return None

    def _validation_error_config(self, location: tuple[str | int, ...]) -> str | None:
        """Read possible config options, retaining parent options for nested values."""
        model = self._validation_model()
        if model is None or not is_pydantic_dataclass(model):
            return None

        fields = model.__pydantic_fields__
        metadata: dict[str, JsonValue] = {}
        options: JsonValue = []
        for part in location:
            if isinstance(part, int):
                continue
            field = fields.get(part)
            properties = metadata.get("properties", {})
            if not isinstance(properties, dict):
                raise TypeError("Validation config properties must be a dictionary")
            child = properties.get(part)
            if child is None:
                if field is None:
                    break
                field_metadata = field.json_schema_extra
                child = field_metadata if isinstance(field_metadata, dict) else {}
            metadata = child if isinstance(child, dict) else {}
            options = metadata.get("config", options)
            annotation = field.annotation if field is not None else None
            fields = (
                annotation.__pydantic_fields__
                if isinstance(annotation, type) and is_pydantic_dataclass(annotation)
                else {}
            )
        return self._format_config_options(options)

    @staticmethod
    def _format_config_options(options: JsonValue) -> str | None:
        """Render the config options that could supply a field's value."""
        if not isinstance(options, list) or not all(isinstance(name, str) for name in options):
            raise TypeError("Validation config options must be a list of strings")
        return " or ".join(f"'{name}'" for name in options) or None

    def _format_validation_error(self, exc: ValidationError) -> str:
        """Preserve paths and reasons, adding possible config options without input metadata."""
        details = []
        for error in exc.errors(include_url=False, include_input=False, include_context=False):
            location = ".".join(str(part) for part in error["loc"])
            detail = f"{location}: {error['msg']}" if location else error["msg"]
            config = self._validation_error_config(error["loc"])
            details.append(f"{detail} (possible config sources: {config})" if config else detail)
        return f"{exc.title}: {'; '.join(details)}"

    @property
    def details(self) -> str:
        """Return the full diagnostic message."""
        return self._details

    @property
    def juju_status_msg(self) -> str:
        """Return the validation error count and a debug-log hint.

        Counts come from the supplied Pydantic validation call, not from distinct
        fields or subsequent validation calls.
        """
        suffix = "" if self._error_count == 1 else "s"
        return f"{self._error_count} validation error{suffix}; see debug-log"


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
