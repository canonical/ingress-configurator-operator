# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for parsing gateway-route state fields."""

from unittest.mock import Mock

import pytest
from charms.traefik_k8s.v2.ingress import IngressRequirerAppData, IngressRequirerData
from ops import CharmBase
from pydantic import Field, TypeAdapter, ValidationError
from pydantic.dataclasses import dataclass

from state.gateway_route import GatewayRouteState


@pytest.mark.parametrize(
    "field, raw_value, expected",
    [
        ("backend_port", 8080, 8080),
        ("paths", " /api, , /other, ", ["/api", "/other"]),
        ("paths", None, ["/"]),
        ("paths", "", ["/"]),
        ("paths", " , , ", ["/"]),
        ("paths", ["/api", "/other"], ["/api", "/other"]),
        ("paths", [], []),
        (
            "additional_hostnames",
            "api.example.com,other.example.com",
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


@pytest.mark.parametrize("raw_paths", [None, "", " , , "])
def test_gateway_empty_paths_use_declared_field_default(raw_paths):
    """Use the field's declared default rather than a fallback inside the validator."""

    @dataclass(frozen=True)
    class CustomDefaultGatewayRouteState(GatewayRouteState):
        """Gateway state with a different declared path default."""

        paths: list[str] = Field(default=["/custom"])

    state = TypeAdapter(CustomDefaultGatewayRouteState).validate_python(
        {
            "application_name": "backend",
            "model_name": "test-model",
            "hostname": None,
            "backend_protocol": "http",
            "backend_port": 8080,
            "paths": raw_paths,
        }
    )

    assert state.paths == ["/custom"]


@pytest.mark.parametrize("raw_fields", [{}, {"paths": None}])
def test_gateway_path_defaults_are_not_shared(raw_fields):
    """Give each state its own path list, including when a validator requests the default."""
    data = {
        "application_name": "backend",
        "model_name": "test-model",
        "hostname": None,
        "backend_protocol": "http",
        "backend_port": 8080,
        **raw_fields,
    }
    adapter = TypeAdapter(GatewayRouteState)
    first = adapter.validate_python(data)
    second = adapter.validate_python(data)

    assert first.paths is not second.paths
    first.paths.append("/extra")
    assert second.paths == ["/"]


@pytest.mark.parametrize(
    "paths, expected_paths",
    [
        (" /api, , /other, ", ["/api", "/other"]),
        ("", ["/"]),
        (None, ["/"]),
        (" , , ", ["/"]),
    ],
)
def test_gateway_adapter_parses_config_and_preserves_relation_data(paths, expected_paths):
    """Normalize gateway config while taking backend details from the ingress relation."""
    charm = Mock(CharmBase)
    charm.config = {
        "hostname": "example.com",
        "backend-protocol": "http",
        "additional-hostnames": "api.example.com,other.example.com",
        "paths": paths,
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
    assert state.paths == expected_paths


def test_gateway_hostnames_do_not_trim_individual_items():
    """Keep hostname parsing distinct from gateway path and backend normalization."""
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(GatewayRouteState).validate_python(
            {
                "application_name": "backend",
                "model_name": "test-model",
                "hostname": None,
                "backend_protocol": "http",
                "backend_port": 8080,
                "additional_hostnames": "example.com, other.example.com",
            }
        )

    assert exc_info.value.errors()[0]["loc"] == ("additional_hostnames", 1)
