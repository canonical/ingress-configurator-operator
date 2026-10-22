# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for parsing gateway-route state fields."""

from unittest.mock import Mock

import pytest
from charms.traefik_k8s.v2.ingress import IngressRequirerAppData, IngressRequirerData
from ops import CharmBase
from pydantic import TypeAdapter

from state.gateway_route import GatewayRouteState


@pytest.mark.parametrize(
    "field, raw_value, expected",
    [
        ("paths", " /api, , /other, ", ["/api", "/other"]),
        ("paths", None, ["/"]),
        ("paths", "", ["/"]),
        ("paths", " , , ", ["/"]),
        ("paths", ["/api", "/other"], ["/api", "/other"]),
        ("paths", [], []),
        (
            "additional_hostnames",
            " api.example.com, , other.example.com, ",
            ["api.example.com", "other.example.com"],
        ),
        ("additional_hostnames", ["api.example.com"], ["api.example.com"]),
        ("additional_hostnames", None, []),
        ("additional_hostnames", "", []),
    ],
)
def test_gateway_state_parses_raw_fields(field, raw_value, expected):
    """Normalize raw config while accepting already-parsed values."""
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


def test_gateway_adapter_parses_config_and_preserves_relation_data():
    """Normalize gateway config while taking backend details from the ingress relation."""
    charm = Mock(CharmBase)
    charm.config = {
        "hostname": "example.com",
        "backend-protocol": "http",
        "additional-hostnames": "api.example.com,other.example.com",
        "paths": " /api, , /other, ",
    }
    ingress_data = IngressRequirerData(
        app=IngressRequirerAppData.model_validate(
            {
                "name": "backend",
                "model": "test-model",
                "port": 8080,
                "strip-prefix": True,
            }
        ),
        units=[],
    )

    state = GatewayRouteState.build_for_adapter_mode(charm, ingress_data)

    assert state.application_name == "backend"
    assert state.model_name == "test-model"
    assert state.backend_port == 8080
    assert state.strip_prefix is True
    assert state.backend_protocol == "http"
    assert state.hostname == "example.com"
    assert state.additional_hostnames == ["api.example.com", "other.example.com"]
    assert state.paths == ["/api", "/other"]
