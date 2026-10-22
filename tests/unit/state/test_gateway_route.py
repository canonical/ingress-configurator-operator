# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for parsing gateway-route state fields."""

from unittest.mock import Mock

import pytest
from ops import CharmBase
from pydantic import TypeAdapter, ValidationError

from state.gateway_route import GatewayRouteState, InvalidGatewayRouteStateError


@pytest.mark.parametrize(
    "field, raw_value, expected",
    [
        ("backend_port", " 8080, , ", 8080),
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


@pytest.mark.parametrize(
    "addresses, expected_type",
    [
        (" 10.0.0.1, , 10.0.0.2, ", "IPv4"),
        (" 2001:db8::1, , 2001:db8::2, ", "IPv6"),
    ],
)
def test_gateway_integrator_normalizes_backend_config(addresses, expected_type):
    """Keep gateway-specific trimming, empty-item removal, and address families."""
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": addresses,
        "backend-ports": " , 8080, ",
        "paths": " /api, , /other, ",
    }
    charm.app.name = "backend"
    charm.model.name = "test-model"

    state = GatewayRouteState.build_for_integrator_mode(charm)

    assert state.backend_port == 8080
    assert state.paths == ["/api", "/other"]
    assert state.integrator_state is not None
    assert state.integrator_state.address_type == expected_type
    assert [str(address) for address in state.integrator_state.backend_addresses] == [
        address.strip() for address in addresses.split(",") if address.strip()
    ]


@pytest.mark.parametrize(
    "ports, reason",
    [
        (None, "Value error, gateway-route requires exactly one port in backend-ports."),
        ("", "Value error, gateway-route requires exactly one port in backend-ports."),
        (" , , ", "Value error, gateway-route requires exactly one port in backend-ports."),
        ("80,443", "Value error, gateway-route requires exactly one port in backend-ports."),
        ("invalid", "Value error, invalid literal for int() with base 10: 'invalid'"),
        ("8080.0", "Value error, invalid literal for int() with base 10: '8080.0'"),
        ("0", "Input should be greater than 0"),
        ("65536", "Input should be less than or equal to 65535"),
    ],
)
def test_gateway_integrator_reports_port_validation_errors(ports, reason):
    """Wrap all port failures consistently, retaining the complete diagnostic."""
    charm = Mock(CharmBase)
    charm.config = {"backend-addresses": "10.0.0.1", "backend-ports": ports}
    charm.app.name = "backend"
    charm.model.name = "test-model"

    with pytest.raises(InvalidGatewayRouteStateError) as exc_info:
        GatewayRouteState.build_for_integrator_mode(charm)

    assert str(exc_info.value) == "Invalid gateway-route configuration; see debug-log"
    assert exc_info.value.details == (
        f"Invalid gateway-route configuration: GatewayRouteState: backend_port: {reason}"
    )
    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_gateway_integrator_collects_port_and_hostname_errors():
    """Report a malformed port together with other invalid state fields."""
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "10.0.0.1",
        "backend-ports": "invalid",
        "hostname": "invalid hostname!",
    }
    charm.app.name = "backend"
    charm.model.name = "test-model"

    with pytest.raises(InvalidGatewayRouteStateError) as exc_info:
        GatewayRouteState.build_for_integrator_mode(charm)

    assert str(exc_info.value) == "2 validation errors; see debug-log"
    assert exc_info.value.details == (
        "Invalid gateway-route configuration: GatewayRouteState: "
        "hostname: Value error, Invalid domain: invalid hostname!; "
        "backend_port: Value error, invalid literal for int() with base 10: 'invalid'"
    )


@pytest.mark.parametrize("addresses", [None, "", " , , ", "10.0.0.1,::1"])
def test_gateway_integrator_rejects_empty_or_mixed_family_addresses(addresses):
    """Require nonempty backend addresses from a single IP family."""
    charm = Mock(CharmBase)
    charm.config = {"backend-addresses": addresses, "backend-ports": "8080"}
    charm.app.name = "backend"
    charm.model.name = "test-model"

    with pytest.raises(InvalidGatewayRouteStateError) as exc_info:
        GatewayRouteState.build_for_integrator_mode(charm)

    assert isinstance(exc_info.value.__cause__, ValidationError)


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
