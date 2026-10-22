# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the helpers module."""

import pytest
from pydantic import ValidationError

from helpers import InvalidRouteStateError, truncate_k8s_resource_name
from state.gateway_route import GatewayRouteState, InvalidGatewayRouteStateError
from state.haproxy_route import HaproxyRouteState, InvalidHaproxyRouteStateError
from state.haproxy_route_tcp import HaproxyRouteTcpState, InvalidHaproxyRouteTcpStateError


@pytest.mark.parametrize(
    "fields, expected_status",
    [
        (("port",), "Invalid configuration; see debug-log"),
        (("port", "port"), "2 validation errors; see debug-log"),
    ],
)
def test_config_error_separates_status_from_details(fields, expected_status):
    """The shared exception separates status summaries from complete diagnostics."""
    validation_error = ValidationError.from_exception_data(
        "Example",
        [
            {
                "type": "greater_than",
                "loc": (field,),
                "input": -1,
                "ctx": {"gt": 0},
            }
            for field in fields
        ],
    )

    error = InvalidRouteStateError("Invalid configuration", validation_error=validation_error)

    expected_details = "Invalid configuration: Example: " + "; ".join(
        f"{field}: Input should be greater than 0" for field in fields
    )
    assert error.details == expected_details
    assert error.juju_status_msg == expected_status
    assert str(error) == expected_details


@pytest.mark.parametrize(
    "model, error_type, location, sources",
    [
        (
            HaproxyRouteState,
            InvalidHaproxyRouteStateError,
            ("backend_ports", 0),
            "config 'backend-ports' or ingress 'port' or Kubernetes Service 'nodePort'",
        ),
        (
            HaproxyRouteState,
            InvalidHaproxyRouteStateError,
            ("timeout", "connect"),
            "config 'timeout-connect'",
        ),
        (
            HaproxyRouteTcpState,
            InvalidHaproxyRouteTcpStateError,
            ("health_check", "check_type"),
            "config 'tcp-health-check-type'",
        ),
        (
            HaproxyRouteTcpState,
            InvalidHaproxyRouteTcpStateError,
            ("port_mapping", "frontend", "start"),
            "config 'tcp-port-mapping' or config 'tcp-frontend-port' or config 'tcp-backend-port'",
        ),
        (
            GatewayRouteState,
            InvalidGatewayRouteStateError,
            ("backend_port",),
            "ingress 'port'",
        ),
    ],
)
def test_validation_diagnostics_identify_possible_sources(model, error_type, location, sources):
    """Use field metadata for public source names without discarding missing-field details."""
    exc = ValidationError.from_exception_data(
        model.__name__,
        [{"type": "missing", "loc": location, "input": {}}],
    )

    error = error_type(
        "Invalid configuration",
        validation_error=exc,
    )

    path = ".".join(str(part) for part in location)
    reason = f"{path}: Field required" if path else "Field required"
    assert error.details == (
        f"Invalid configuration: {model.__name__}: {reason} (possible sources: {sources})"
    )
    assert error.juju_status_msg == f"Invalid {sources}; see debug-log"


def test_format_validation_error_preserves_paths_and_reasons():
    """Preserve all locations and reasons without exposing inputs or metadata."""
    exc = ValidationError.from_exception_data(
        "Example",
        [
            {
                "type": "greater_than",
                "loc": ("items", 1),
                "input": -1,
                "ctx": {"gt": 0},
            },
            {
                "type": "too_short",
                "loc": ("ports",),
                "input": [],
                "ctx": {"field_type": "List", "min_length": 1, "actual_length": 0},
            },
            {
                "type": "value_error",
                "loc": (),
                "input": "private-input",
                "ctx": {"error": ValueError("interval, rise, and fall must all be set")},
            },
        ],
    )

    error = InvalidRouteStateError("Invalid configuration", validation_error=exc)

    assert error.details == (
        "Invalid configuration: Example: items.1: Input should be greater than 0; "
        "ports: List should have at least 1 item after validation, not 0; "
        "Value error, interval, rise, and fall must all be set"
    )


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("my-model-my-app-service", id="short name"),
        pytest.param("a" * 63, id="exactly 63 chars"),
    ],
)
def test_truncate_k8s_resource_name_unchanged(name):
    """
    arrange: a name at or below the 63-character limit
    act: call truncate_k8s_resource_name
    assert: the name is returned unchanged
    """
    assert truncate_k8s_resource_name(name) == name


def test_truncate_k8s_resource_name_long_name_at_most_63_chars():
    """
    arrange: a name longer than 63 characters
    act: call truncate_k8s_resource_name
    assert: the result is at most 63 characters
    """
    name = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
    assert len(truncate_k8s_resource_name(name)) <= 63


def test_truncate_k8s_resource_name_long_name_is_deterministic():
    """
    arrange: a name longer than 63 characters
    act: call truncate_k8s_resource_name twice
    assert: the results are identical
    """
    name = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
    assert truncate_k8s_resource_name(name) == truncate_k8s_resource_name(name)


def test_truncate_k8s_resource_name_different_long_names_differ():
    """
    arrange: two different names that are both longer than 63 characters
    act: call truncate_k8s_resource_name on each
    assert: the results are different
    """
    name1 = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
    name2 = "k8s-stg-a-very-long-model-name-my-other-application-ingress-configurator-service"
    assert truncate_k8s_resource_name(name1) != truncate_k8s_resource_name(name2)


def test_truncate_k8s_resource_name_no_trailing_dash_before_suffix():
    """
    arrange: a name where the truncation point falls on a dash
    act: call truncate_k8s_resource_name
    assert: the result contains no double-dash and is at most 63 characters
    """
    name = "a" * 54 + "-" + "b" * 20
    result = truncate_k8s_resource_name(name)
    assert "--" not in result
    assert len(result) <= 63
