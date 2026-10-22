# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for reusable comma-separated field validation."""

import ipaddress

import pytest
from pydantic import TypeAdapter, ValidationError

from state.validators import BackendAddresses, BackendPorts, split_comma_separated


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
