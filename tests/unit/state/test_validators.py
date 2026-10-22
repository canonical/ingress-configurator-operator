# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for reusable comma-separated field validation."""

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
        (" 80, , invalid,443, ", ["80", "invalid", "443"]),
        (["first", "second"], ["first", "second"]),
    ],
)
def test_split_comma_separated(value, expected):
    """Trim string items, skip empty entries, and accept already-parsed lists."""
    assert split_comma_separated(value) == expected


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
