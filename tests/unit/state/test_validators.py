# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for reusable comma-separated field validation."""

import ipaddress
from typing import Annotated

import pytest
from pydantic import BeforeValidator, TypeAdapter, ValidationError

from state.validators import split_comma_separated


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        ("first,second", ["first", "second"]),
        (" first,,second,", ["first", "second"]),
        (" , , ", []),
        (["first", "second"], ["first", "second"]),
    ],
)
def test_split_comma_separated(value, expected):
    """Trim string items, skip empty entries, and accept already-parsed lists."""
    assert split_comma_separated(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        (" , , ", []),
        (" 80, +443, , 8_080, ", [80, 443, 8080]),
    ],
)
def test_split_comma_separated_converts_integers(value: str | None, expected: list[int]) -> None:
    """Convert integer items and ignore empty raw items."""
    assert split_comma_separated(value, convert=int) == expected


def test_split_comma_separated_converts_addresses() -> None:
    """Support converters other than builtin scalar types."""
    result = split_comma_separated(" 10.0.0.1, , 10.0.0.2, ", convert=ipaddress.IPv4Address)

    assert result == [ipaddress.IPv4Address("10.0.0.1"), ipaddress.IPv4Address("10.0.0.2")]


def test_split_comma_separated_propagates_conversion_errors() -> None:
    """Surface converter failures instead of returning partially parsed data."""
    with pytest.raises(ValueError) as exc_info:
        split_comma_separated("80,invalid,443", convert=int)

    assert str(exc_info.value) == "invalid literal for int() with base 10: 'invalid'"


@pytest.mark.parametrize("value", [[80, 443], [" first ", ""], 42, {"port": 80}])
def test_split_comma_separated_preserves_nonstring_inputs(value: object) -> None:
    """Leave parsed lists and invalid input types unchanged for Pydantic."""
    assert split_comma_separated(value) is value


def test_split_comma_separated_retains_item_validation_errors() -> None:
    """Leave parsed-list validation to Pydantic so all item failures are collected."""
    adapter: TypeAdapter[list[int]] = TypeAdapter(
        Annotated[
            list[int],
            BeforeValidator(split_comma_separated),
        ]
    )

    with pytest.raises(ValidationError) as exc_info:
        adapter.validate_python(["invalid", "also-invalid"])

    assert [error["loc"] for error in exc_info.value.errors()] == [(0,), (1,)]
