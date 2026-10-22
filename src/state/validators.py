# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reusable parsing and validation for comma-separated route fields."""

from collections.abc import Callable


def split_comma_separated(value: object, *, convert: Callable[[str], object] = str) -> object:
    """Trim and convert nonempty string items; preserve already-parsed inputs.

    Args:
        value: A comma-separated string, unset value, or already-parsed field input.
        convert: Item converter, defaulting to str. Its exceptions propagate unchanged.

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
