# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for reusable delimited field validation."""

from functools import partial
from typing import Annotated

import pytest
from pydantic import BeforeValidator, TypeAdapter

from helpers import split_delimited


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
def test_split_delimited(value, expected):
    """Trim string items, skip empty entries, and accept already-parsed lists."""
    assert split_delimited(value) == expected


@pytest.mark.parametrize("value", [[80, 443], [" first ", ""], 42, {"port": 80}])
def test_split_delimited_preserves_nonstring_inputs(value: object) -> None:
    """Leave parsed lists and invalid input types unchanged for Pydantic."""
    assert split_delimited(value) is value


def test_split_delimited_accepts_custom_delimiter():
    """Trim and skip empty items when a caller overrides the delimiter."""
    assert split_delimited(" first:: ::second::", delimiter="::") == ["first", "second"]


def test_split_delimited_partial_validates_items():
    """Allow a delimiter to be bound without changing Pydantic's validator signature."""
    adapter: TypeAdapter[list[int]] = TypeAdapter(
        Annotated[
            list[int],
            BeforeValidator(partial(split_delimited, delimiter=";")),
        ]
    )

    assert adapter.validate_python(" 80; ;443; ") == [80, 443]
