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


def split_trimmed_comma_separated(value: object, convert: Callable[[str], object]) -> object:
    """Convert trimmed string items; preserve other inputs for Pydantic to validate.

    Args:
        value: A comma-separated string, unset value, or already-parsed field input.
        convert: Callable that converts each trimmed item. Its exceptions propagate unchanged.

    Returns:
        Converted items for strings, an empty list for None, or the original value.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [convert(item.strip()) for item in value.split(",") if item.strip()]
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
