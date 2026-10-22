# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Parsing helpers for comma-separated route fields."""


def split_comma_separated(value: object) -> object:
    """Split trimmed nonempty string items; preserve already-parsed inputs.

    Args:
        value: A comma-separated string, unset value, or already-parsed field input.

    Returns:
        Trimmed nonempty items for strings, an empty list for None, or the original value.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value
