# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for parsing gateway-route state fields."""

import pytest
from pydantic import TypeAdapter

from state.gateway_route import GatewayRouteState


@pytest.mark.parametrize(
    "field, raw_value, expected",
    [
        ("paths", " /api, , /other, ", ["/api", "/other"]),
        ("paths", "", ["/"]),
        ("paths", " , , ", ["/"]),
        (
            "additional_hostnames",
            " api.example.com, , other.example.com, ",
            ["api.example.com", "other.example.com"],
        ),
        ("additional_hostnames", "", []),
    ],
)
def test_gateway_state_parses_raw_fields(field, raw_value, expected):
    """Normalize raw string config."""
    state = TypeAdapter(GatewayRouteState).validate_python(
        {
            "application_name": "backend",
            "model_name": "test-model",
            "hostname": "example.com",
            "backend_protocol": "http",
            "backend_port": 8080,
            field: raw_value,
        }
    )

    assert getattr(state, field) == expected
