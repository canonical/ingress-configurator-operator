# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for HaproxyRouteState in integrator mode (for_integrator_mode)."""

from unittest.mock import Mock

import pytest
from charms.haproxy.v2.haproxy_route import LoadBalancingAlgorithm
from ops import CharmBase

from state.haproxy_route import (
    HaproxyRouteState,
    InvalidHaproxyRouteBackendStateError,
    InvalidHaproxyRouteStateError,
)


def _make_integrator_state(charm):
    """Build HaproxyRouteState for integrator mode."""
    return HaproxyRouteState.for_integrator_mode(charm)


def test_integrator_state_from_charm():
    """
    arrange: mock a charm with backend configuration
    act: instantiate a State via for_integrator_mode
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "retry-count": 1,
        "retry-redispatch": True,
        "http-server-close": True,
    }
    charm_state = _make_integrator_state(charm)

    assert [str(address) for address in charm_state.backend_addresses] == charm.config.get(
        "backend-addresses"
    ).split(",")
    assert charm_state.backend_ports == [int(charm.config.get("backend-ports"))]
    assert charm_state.backend_protocol == "http"
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.redispatch == charm.config.get("retry-redispatch")
    assert charm_state.http_server_close == charm.config.get("http-server-close")
    assert charm_state.allow_http is False


def test_state_from_charm_no_backend():
    """
    arrange: mock a charm with no backend configuration
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {}
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_address():
    """
    arrange: mock a charm with an invalid backend address
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "invalid",
        "backend-ports": "8080",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_paths():
    """
    arrange: mock a charm with invalid paths configuration
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "paths": "invalid path",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_port():
    """
    arrange: mock a charm with an out-of-range backend port
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "99999",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_protocol():
    """Check that backend-protocol config field is validated."""
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "80",
        "backend-protocol": "gopher",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_check_path():
    """
    arrange: mock a charm with an invalid health-check-path
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-path": "invalid$path",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_check_port():
    """
    arrange: mock a charm with an out-of-range health-check-port
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-port": 99999,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_check_interval():
    """
    arrange: mock a charm with an invalid health-check-interval (zero)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-interval": 0,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_check_rise():
    """
    arrange: mock a charm with an invalid health-check-rise (zero)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-rise": 0,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_check_fall():
    """
    arrange: mock a charm with an invalid health-check-fall (zero)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-fall": 0,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_missing_check_interval():
    """
    arrange: mock a charm with rise and fall set but interval missing
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-rise": 3,
        "health-check-fall": 4,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_missing_check_rise():
    """
    arrange: mock a charm with interval and fall set but rise missing
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-interval": 20,
        "health-check-fall": 4,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_missing_check_fall():
    """
    arrange: mock a charm with interval and rise set but fall missing
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "health-check-interval": 20,
        "health-check-rise": 3,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_retry_count():
    """
    arrange: mock a charm with an invalid retry-count (zero)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "retry-count": 0,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_timeout_server():
    """
    arrange: mock a charm with an invalid timeout-server (negative)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-server": -1,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_timeout_connect():
    """
    arrange: mock a charm with an invalid timeout-connect (negative)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-connect": -1,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_timeout_queue():
    """
    arrange: mock a charm with an invalid timeout-queue (negative)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-queue": -1,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_hostname():
    """
    arrange: mock a charm with an invalid hostname
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "hostname": "invalid$hostname",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_additional_hostnames():
    """
    arrange: mock a charm with invalid additional-hostnames
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "hostname": "valid.example.com",
        "additional-hostnames": "invalid$\\",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


@pytest.mark.parametrize(
    "hostname",
    [
        pytest.param("*.example.com", id="wildcard_hostname"),
        pytest.param("*.subdomain.example.com", id="wildcard_subdomain"),
        pytest.param("example.com", id="standard_hostname"),
        pytest.param("subdomain.example.com", id="standard_subdomain"),
        pytest.param("a.b.c.d.example.com", id="multi_level_subdomain"),
    ],
)
def test_state_from_charm_valid_hostname_with_wildcard(hostname):
    """Test State creation with valid hostnames including wildcards.

    arrange: mock a charm with valid hostname including wildcards
    act: instantiate a State via for_integrator_mode
    assert: state is created successfully
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "hostname": hostname,
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.hostname == hostname


@pytest.mark.parametrize(
    "invalid_hostname",
    [
        pytest.param("**.example.com", id="double_wildcard"),
        pytest.param("*example.com", id="wildcard_without_dot"),
        pytest.param("sub.*.example.com", id="wildcard_not_at_beginning"),
        pytest.param("*.*.example.com", id="multiple_wildcards"),
        pytest.param("example.*.com", id="wildcard_in_middle"),
        pytest.param("*.com", id="wildcard_tld"),
    ],
)
def test_state_from_charm_invalid_hostname_wildcard(invalid_hostname):
    """Test State creation fails with invalid wildcard hostname.

    arrange: mock a charm with invalid wildcard hostname
    act: instantiate a State via for_integrator_mode
    assert: InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "hostname": invalid_hostname,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


@pytest.mark.parametrize(
    "additional_hostnames",
    [
        pytest.param("*.example.com,*.other.com", id="multiple_wildcards"),
        pytest.param("*.subdomain.example.com,normal.example.com", id="mixed_wildcard_standard"),
        pytest.param("example.com,subdomain.example.com", id="multiple_standard"),
    ],
)
def test_state_from_charm_valid_additional_hostnames_with_wildcard(additional_hostnames):
    """Test State creation with valid additional hostnames including wildcards.

    arrange: mock a charm with valid additional hostnames including wildcards
    act: instantiate a State via for_integrator_mode
    assert: state is created successfully
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "additional-hostnames": additional_hostnames,
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.additional_hostnames == additional_hostnames.split(",")


@pytest.mark.parametrize(
    "invalid_additional_hostnames",
    [
        pytest.param("**.example.com", id="double_wildcard"),
        pytest.param("*example.com,valid.com", id="one_invalid_one_valid"),
        pytest.param("valid.com,*.*.example.com", id="valid_and_multiple_wildcards"),
    ],
)
def test_state_from_charm_invalid_additional_hostnames_wildcard(invalid_additional_hostnames):
    """Test State creation fails with invalid wildcard in additional hostnames.

    arrange: mock a charm with invalid wildcard in additional hostnames
    act: instantiate a State via for_integrator_mode
    assert: InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "additional-hostnames": invalid_additional_hostnames,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_port_invalid_int():
    """
    arrange: mock a charm with a non-integer backend port
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "invalid",
    }
    with pytest.raises(InvalidHaproxyRouteBackendStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_load_balancing_algorithm():
    """
    arrange: mock a charm with an invalid load-balancing-algorithm
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "load-balancing-algorithm": "invalid",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_invalid_load_balancing_configuration():
    """
    arrange: mock a charm with incompatible load-balancing configuration combinations
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised for each invalid combination
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "load-balancing-algorithm": "leastconn",
        "load-balancing-cookie": "TEST",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)

    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "load-balancing-algorithm": "leastconn",
        "load-balancing-consistent-hashing": True,
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_load_balancing_default_value():
    """
    arrange: mock a charm with no load-balancing configuration
    act: instantiate a State via for_integrator_mode
    assert: the default algorithm is LEASTCONN
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.load_balancing_configuration.algorithm == LoadBalancingAlgorithm.LEASTCONN


@pytest.mark.parametrize(
    "path_rewrite_expression,expected_result",
    [
        pytest.param(
            "%[path,regsub(^/old/(.*),/new/$1)]",
            ["%[path,regsub(^/old/(.*),/new/$1)]"],
            id="one_path_expressions",
        ),
        pytest.param(
            "%[path,regsub(^/,/new)]\\n%[path,regsub(^/api,/v1)]",
            ["%[path,regsub(^/,/new)]", "%[path,regsub(^/api,/v1)]"],
            id="two_path_expressions",
        ),
    ],
)
def test_state_from_charm_path_rewrite(path_rewrite_expression: str, expected_result: list[str]):
    """
    arrange: mock a charm with valid HAProxy set-path grammar expressions
    act: instantiate a State via for_integrator_mode
    assert: the path_rewrite_expressions contains the expressions
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "path-rewrite-expressions": path_rewrite_expression,
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.path_rewrite_expressions == expected_result


@pytest.mark.parametrize(
    "header_rewrite_expression,expected_result",
    [
        pytest.param(
            "X-Forwarded-For:%[src]",
            [("X-Forwarded-For", "%[src]")],
            id="one_header_expressions",
        ),
        pytest.param(
            "X-Forwarded-For:%[src]\\nHost:example.com\\nDate:Wed, 15 Jan 2025 10:20:30 GMT",
            [
                ("X-Forwarded-For", "%[src]"),
                ("Host", "example.com"),
                ("Date", "Wed, 15 Jan 2025 10:20:30 GMT"),
            ],
            id="several_header_expressions",
        ),
    ],
)
def test_state_from_charm_header_rewrite(
    header_rewrite_expression: str, expected_result: list[tuple[str, str]]
):
    """
    arrange: mock a charm with valid HAProxy set-header grammar expressions
    act: instantiate a State via for_integrator_mode
    assert: the header_rewrite_expressions contains the expressions
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "header-rewrite-expressions": header_rewrite_expression,
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.header_rewrite_expressions == expected_result


def test_state_from_charm_invalid_header_rewrite():
    """
    arrange: mock a charm with an invalid header-rewrite-expressions value (missing colon)
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "header-rewrite-expressions": "X-Forwarded-For",
    }
    with pytest.raises(InvalidHaproxyRouteStateError):
        _make_integrator_state(charm)


def test_state_from_charm_external_grpc_port_nominal():
    """
    arrange: mock a charm with valid external-grpc-port and https protocol
    act: instantiate a State via for_integrator_mode
    assert: the external_grpc_port is set correctly
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "8080",
        "backend-protocol": "https",
        "external-grpc-port": 50051,
    }
    charm_state = _make_integrator_state(charm)
    assert charm_state.external_grpc_port == 50051


def test_state_from_charm_invalid_external_grpc_port_and_http():
    """
    arrange: mock a charm with external-grpc-port but http protocol
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised with ValueError as cause
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "8080",
        "backend-protocol": "http",
        "external-grpc-port": 50051,
    }
    with pytest.raises(InvalidHaproxyRouteStateError) as exc_info:
        _make_integrator_state(charm)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "external_grpc_port can only be set when backend_protocol is 'https'" in str(
        exc_info.value.__cause__
    )


def test_state_from_charm_invalid_external_grpc_port_invalid_and_allow_http():
    """
    arrange: mock a charm with external-grpc-port and allow-http both set
    act: instantiate a State via for_integrator_mode
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "8080",
        "backend-protocol": "https",
        "external-grpc-port": 50051,
        "allow-http": True,
    }
    with pytest.raises(InvalidHaproxyRouteStateError) as exc_info:
        _make_integrator_state(charm)
    assert "external_grpc_port cannot be set when allow_http is True." in str(
        exc_info.value.__cause__
    )
