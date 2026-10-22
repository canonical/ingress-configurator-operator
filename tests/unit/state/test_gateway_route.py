# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for parsing gateway-route state fields."""

from unittest.mock import Mock

import pytest
from charms.traefik_k8s.v2.ingress import IngressRequirerAppData, IngressRequirerData
from ops import CharmBase

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
    """Normalize raw string configuration through the adapter state builder."""
    charm = Mock(CharmBase)
    charm.config = {
        "hostname": "example.com",
        "backend-protocol": "http",
        field.replace("_", "-"): raw_value,
    }
    ingress_data = IngressRequirerData(
        app=IngressRequirerAppData(name="backend", model="test-model", port=8080),
        units=[],
    )
    state = GatewayRouteState.build_for_adapter_mode(charm, ingress_data)

    assert getattr(state, field) == expected
