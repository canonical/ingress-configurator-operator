# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for reusable comma-separated field validation."""

import ipaddress
from functools import partial
from typing import Annotated

import pytest
from pydantic import BeforeValidator, TypeAdapter, ValidationError

from state.validators import (
    BackendAddresses,
    BackendPorts,
    split_comma_separated,
    split_trimmed_comma_separated,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        ("first,second", ["first", "second"]),
        (" first,,second,", [" first", "", "second", ""]),
        (["first", "second"], ["first", "second"]),
    ],
)
def test_split_comma_separated(value, expected):
    """Preserve existing comma-separated syntax and already-parsed lists."""
    assert split_comma_separated(value) == expected


def test_split_comma_separated_does_not_modify_lists():
    """Leave list inputs untouched for the field's item validators."""
    value = ["first", "second"]

    assert split_comma_separated(value) is value


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        (" , , ", []),
        (" 80, +443, , 8_080, ", [80, 443, 8080]),
    ],
)
def test_split_trimmed_comma_separated_converts_integers(
    value: str | None, expected: list[int]
) -> None:
    """Convert integer items and ignore empty raw items."""
    assert split_trimmed_comma_separated(value, convert=int) == expected


def test_split_trimmed_comma_separated_converts_strings() -> None:
    """Keep trimmed string results when using the string converter."""
    assert split_trimmed_comma_separated(" first, , second, ", convert=str) == [
        "first",
        "second",
    ]


def test_split_trimmed_comma_separated_converts_addresses() -> None:
    """Support converters other than builtin scalar types."""
    result = split_trimmed_comma_separated(
        " 10.0.0.1, , 10.0.0.2, ", convert=ipaddress.IPv4Address
    )

    assert result == [ipaddress.IPv4Address("10.0.0.1"), ipaddress.IPv4Address("10.0.0.2")]


def test_split_trimmed_comma_separated_propagates_conversion_errors() -> None:
    """Surface converter failures instead of returning partially parsed data."""
    with pytest.raises(ValueError) as exc_info:
        split_trimmed_comma_separated("80,invalid,443", convert=int)

    assert str(exc_info.value) == "invalid literal for int() with base 10: 'invalid'"


@pytest.mark.parametrize("value", [[80, 443], [" first ", ""], 42, {"port": 80}])
def test_split_trimmed_comma_separated_preserves_nonstring_inputs(value: object) -> None:
    """Leave parsed lists and invalid input types unchanged for Pydantic."""
    assert split_trimmed_comma_separated(value, convert=str) is value


def test_split_trimmed_partial_retains_item_validation_errors() -> None:
    """A bound converter must leave parsed-list validation to Pydantic."""
    adapter: TypeAdapter[list[int]] = TypeAdapter(
        Annotated[
            list[int],
            BeforeValidator(partial(split_trimmed_comma_separated, convert=str)),
        ]
    )

    with pytest.raises(ValidationError) as exc_info:
        adapter.validate_python(["invalid", "also-invalid"])

    assert [error["loc"] for error in exc_info.value.errors()] == [(0,), (1,)]


@pytest.mark.parametrize(
    "value",
    [
        "10.0.0.1,2001:db8::1",
        ["10.0.0.1", "2001:db8::1"],
        [ipaddress.ip_address("10.0.0.1"), ipaddress.ip_address("2001:db8::1")],
    ],
)
def test_backend_addresses_accept_strings_and_lists(value):
    """Parse addresses while retaining support for resolved relation inputs."""
    addresses = TypeAdapter(BackendAddresses).validate_python(value)

    assert addresses == [ipaddress.ip_address("10.0.0.1"), ipaddress.ip_address("2001:db8::1")]


@pytest.mark.parametrize("value", [None, "", [], "invalid", " 10.0.0.1", "10.0.0.1,"])
def test_backend_addresses_reject_invalid_input(value):
    """Keep non-empty address constraints and existing whitespace behavior."""
    with pytest.raises(ValidationError):
        TypeAdapter(BackendAddresses).validate_python(value)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("80,443", [80, 443]),
        (" 80 ,+443,8_080", [80, 443, 8080]),
        ([80, 443], [80, 443]),
        (["80", "443"], [80, 443]),
    ],
)
def test_backend_ports_accept_strings_and_lists(value, expected):
    """Retain integer conversion and support already-parsed port lists."""
    assert TypeAdapter(BackendPorts).validate_python(value) == expected


@pytest.mark.parametrize("value", [None, "", [], "invalid", "8080.0", "80,", "0", "65536", [1.5]])
def test_backend_ports_reject_invalid_input(value):
    """Reject invalid syntax, fractional ports, and ports outside the valid range."""
    with pytest.raises(ValidationError):
        TypeAdapter(BackendPorts).validate_python(value)
