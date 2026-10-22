# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reusable parsing and validation for comma-separated route fields."""

from collections.abc import Callable
from typing import Annotated

from annotated_types import Len
from pydantic import BeforeValidator, Field
from pydantic.networks import IPvAnyAddress


def split_comma_separated(value: object) -> object:
    """Split string inputs without trimming items; preserve already-parsed values.

    Args:
        value: A comma-separated string, parsed list, or unset value.

    Returns:
        A list for string or unset inputs, otherwise the original value.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return value.split(",") if value else []
    return value


def split_trimmed_comma_separated[T](value: str | None, convert: Callable[[str], T]) -> list[T]:
    """Split trimmed nonempty items and convert each to the requested type.

    Args:
        value: A comma-separated string or unset value.
        convert: Callable that converts each trimmed item. Its exceptions propagate unchanged.

    Returns:
        Converted items, or an empty list for unset or empty input.
    """
    if value is None:
        return []
    return [convert(item.strip()) for item in value.split(",") if item.strip()]


def normalize_trimmed_comma_separated(value: object) -> object:
    """Parse raw strings while leaving other inputs for Pydantic to validate.

    Args:
        value: Raw field input, including already-parsed lists.

    Returns:
        Trimmed nonempty items for string or unset input, otherwise the original value.
    """
    if value is None or isinstance(value, str):
        return split_trimmed_comma_separated(value, convert=str)
    return value


def parse_integer(value: object) -> object:
    """Convert string integers without accepting fractional string syntax.

    Args:
        value: A string integer or a value for Pydantic to validate.

    Returns:
        The parsed integer for strings, otherwise the original value.

    Raises:
        ValueError: If a string cannot be parsed as an integer.
    """
    return int(value) if isinstance(value, str) else value


BackendAddresses = Annotated[
    list[IPvAnyAddress], Len(min_length=1), BeforeValidator(split_comma_separated)
]
BackendPorts = Annotated[
    list[Annotated[int, BeforeValidator(parse_integer), Field(gt=0, le=65535)]],
    Len(min_length=1),
    BeforeValidator(split_comma_separated),
]
