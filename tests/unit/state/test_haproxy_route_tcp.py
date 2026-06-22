# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the haproxy_route_tcp module."""

from unittest.mock import Mock

import pytest
from charms.haproxy.v1.haproxy_route_tcp import LoadBalancingAlgorithm, PortMapping
from ops import CharmBase

from state.haproxy_route_tcp import (
    HaproxyRouteTcpState,
    InvalidHaproxyRouteTcpStateError,
)


def _make_tcp_integrator_state(charm):
    """Build HaproxyRouteTcpState for integrator mode."""
    return HaproxyRouteTcpState.build_for_integrator_mode(charm)


def test_haproxy_route_tcp_requirements_for_integrator_mode():
    """
    arrange: mock a charm with valid TCP configuration
    act: instantiate HaproxyRouteTcpRequirements
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.10,192.168.1.11",
        "tcp-frontend-port": 8443,
        "tcp-backend-port": 443,
        "tcp-tls-terminate": True,
        "tcp-hostname": "example.com",
        "tcp-retry-count": 3,
        "tcp-retry-redispatch": True,
        "tcp-load-balancing-algorithm": "roundrobin",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert [str(addr) for addr in requirements.backend_addresses] == [
        "192.168.1.10",
        "192.168.1.11",
    ]
    assert requirements.port == 8443
    assert requirements.backend_port == 443
    assert requirements.tls_terminate is True
    assert requirements.hostname == "example.com"
    assert requirements.retry.count == 3
    assert requirements.retry.redispatch is True
    assert requirements.load_balancing_configuration.algorithm == LoadBalancingAlgorithm.ROUNDROBIN
    assert requirements.load_balancing_configuration.consistent_hashing is False
    assert requirements.enforce_tls is True
    assert requirements.proxy_protocol is False


def test_haproxy_route_tcp_invalid_algorithm():
    """
    arrange: mock a charm with invalid load balancing algorithm
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "10.0.0.1",
        "tcp-frontend-port": 8443,
        "tcp-backend-port": 443,
        "tcp-tls-terminate": True,
        "tcp-hostname": "example.com",
        "tcp-load-balancing-algorithm": "invalid",
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid load balancing algorithm" in str(exc_info.value)


def test_haproxy_route_tcp_requirements_for_integrator_mode_no_tls():
    """
    arrange: mock a charm with TCP configuration without TLS termination
    act: instantiate HaproxyRouteTcpRequirements
    assert: tls_terminate is False
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "10.0.0.1",
        "tcp-frontend-port": 9000,
        "tcp-backend-port": 9001,
        "tcp-tls-terminate": False,
        "tcp-enforce-tls": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert [str(addr) for addr in requirements.backend_addresses] == ["10.0.0.1"]
    assert requirements.port == 9000
    assert requirements.backend_port == 9001
    assert requirements.tls_terminate is False
    assert requirements.hostname is None


def test_haproxy_route_tcp_requirements_for_integrator_mode_ipv6():
    """
    arrange: mock a charm with IPv6 addresses
    act: instantiate HaproxyRouteTcpRequirements
    assert: IPv6 addresses are correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "2001:db8::1,2001:db8::2",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": "ipv6.example.com",
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert [str(addr) for addr in requirements.backend_addresses] == ["2001:db8::1", "2001:db8::2"]
    assert requirements.port == 443
    assert requirements.backend_port == 8443


@pytest.mark.parametrize(
    "hostname",
    [
        "*.example.com",
        "*.subdomain.example.com",
        "example.com",
        "subdomain.example.com",
        "a.b.c.d.example.com",
    ],
)
def test_haproxy_route_tcp_requirements_valid_wildcard_sni(hostname):
    """
    arrange: mock a charm with valid SNI hostname (including wildcards)
    act: instantiate HaproxyRouteTcpRequirements
    assert: hostname is accepted
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": hostname,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.hostname == hostname


@pytest.mark.parametrize(
    "invalid_hostname",
    [
        "*.com",
        "*.*.example.com",
        "**.example.com",
        "*example.com",
        "sub.*.example.com",
        "example.*.com",
    ],
)
def test_haproxy_route_tcp_requirements_invalid_wildcard_sni(invalid_hostname):
    """
    arrange: mock a charm with invalid wildcard SNI hostname
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": invalid_hostname,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid haproxy-route-tcp configuration" in str(exc_info.value)


def test_haproxy_route_tcp_requirements_empty_backend_addresses():
    """
    arrange: mock a charm without backend addresses
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": None,
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid haproxy-route-tcp configuration" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_address",
    [
        "not-an-ip",
        "999.999.999.999",
        "192.168.1",
        "invalid,192.168.1.1",
    ],
)
def test_haproxy_route_tcp_requirements_invalid_backend_address(invalid_address):
    """
    arrange: mock a charm with invalid backend address
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": invalid_address,
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid load balancing algorithm" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_port",
    [
        0,
        -1,
        65536,
        99999,
    ],
)
def test_haproxy_route_tcp_requirements_invalid_frontend_port(invalid_port):
    """
    arrange: mock a charm with invalid frontend port
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": invalid_port,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid tcp-frontend-port or tcp-backend-port" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_port",
    [
        0,
        -1,
        65536,
        99999,
    ],
)
def test_haproxy_route_tcp_requirements_invalid_backend_port(invalid_port):
    """
    arrange: mock a charm with invalid backend port
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": invalid_port,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid tcp-frontend-port or tcp-backend-port" in str(exc_info.value)


def test_haproxy_route_tcp_requirements_valid_port_boundaries():
    """
    arrange: mock a charm with valid port boundary values
    act: instantiate HaproxyRouteTcpRequirements
    assert: requirements are created successfully
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 1,
        "tcp-backend-port": 65535,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.port == 1
    assert requirements.backend_port == 65535


def test_haproxy_route_tcp_requirements_multiple_backend_addresses():
    """
    arrange: mock a charm with multiple backend addresses
    act: instantiate HaproxyRouteTcpRequirements
    assert: all addresses are correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "10.0.0.1,10.0.0.2,10.0.0.3",
        "tcp-frontend-port": 3306,
        "tcp-backend-port": 3306,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert len(requirements.backend_addresses) == 3
    assert [str(addr) for addr in requirements.backend_addresses] == [
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.3",
    ]


def test_haproxy_route_tcp_requirements_mixed_ip_versions():
    """
    arrange: mock a charm with both IPv4 and IPv6 addresses
    act: instantiate HaproxyRouteTcpRequirements
    assert: both address types are correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1,2001:db8::1",
        "tcp-frontend-port": 5432,
        "tcp-backend-port": 5432,
        "tcp-tls-terminate": False,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert len(requirements.backend_addresses) == 2
    assert [str(addr) for addr in requirements.backend_addresses] == [
        "192.168.1.1",
        "2001:db8::1",
    ]


@pytest.mark.parametrize(
    "tls_terminate,hostname,enforce_tls_config,expected_enforce_tls,expected_hostname",
    [
        pytest.param(False, None, False, False, None, id="enforce_tls_false_without_hostname"),
        pytest.param(True, "example.com", True, True, "example.com", id="enforce_tls_default"),
    ],
)
def test_haproxy_route_tcp_requirements_enforce_tls(
    tls_terminate, hostname, enforce_tls_config, expected_enforce_tls, expected_hostname
):
    """
    arrange: mock a charm with various enforce_tls configurations
    act: instantiate HaproxyRouteTcpRequirements
    assert: enforce_tls and hostname have expected values
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": tls_terminate,
        "tcp-enforce-tls": enforce_tls_config,
        "tcp-hostname": hostname,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.enforce_tls is expected_enforce_tls
    assert requirements.hostname == expected_hostname


@pytest.mark.parametrize(
    "health_check_config,expected_interval,expected_rise,expected_fall",
    [
        pytest.param(
            {
                "tcp-health-check-interval": 10,
                "tcp-health-check-rise": 3,
                "tcp-health-check-fall": 5,
            },
            10,
            3,
            5,
            id="with_health_check",
        ),
        pytest.param({}, None, None, None, id="without_health_check"),
    ],
)
def test_haproxy_route_tcp_requirements_health_check_presence(
    health_check_config, expected_interval, expected_rise, expected_fall
):
    """
    arrange: mock a charm with/without health check configuration
    act: instantiate HaproxyRouteTcpRequirements
    assert: health check values match expected
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
        **health_check_config,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.health_check.interval == expected_interval
    assert requirements.health_check.rise == expected_rise
    assert requirements.health_check.fall == expected_fall


@pytest.mark.parametrize(
    "missing_field",
    [
        {"tcp-health-check-interval": 10, "tcp-health-check-rise": 3},
        {"tcp-health-check-interval": 10, "tcp-health-check-fall": 5},
        {"tcp-health-check-rise": 3, "tcp-health-check-fall": 5},
    ],
)
def test_haproxy_route_tcp_requirements_incomplete_health_check(missing_field):
    """
    arrange: mock a charm with incomplete health check configuration
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        **missing_field,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid haproxy-route-tcp configuration" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_value",
    [
        {"tcp-health-check-interval": -1, "tcp-health-check-rise": 3, "tcp-health-check-fall": 5},
        {"tcp-health-check-interval": 10, "tcp-health-check-rise": 0, "tcp-health-check-fall": 5},
        {"tcp-health-check-interval": 10, "tcp-health-check-rise": 3, "tcp-health-check-fall": -5},
    ],
)
def test_haproxy_route_tcp_requirements_invalid_health_check_values(invalid_value):
    """
    arrange: mock a charm with invalid health check values
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        **invalid_value,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid haproxy-route-tcp configuration" in str(exc_info.value)


def test_haproxy_route_tcp_requirements_health_check_with_type_generic():
    """
    arrange: mock a charm with generic health check type and send/expect
    act: instantiate HaproxyRouteTcpRequirements
    assert: health check fields are correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-enforce-tls": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-health-check-interval": 10,
        "tcp-health-check-rise": 3,
        "tcp-health-check-fall": 5,
        "tcp-health-check-type": "generic",
        "tcp-health-check-send": "PING",
        "tcp-health-check-expect": "PONG",
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.health_check.check_type is not None
    assert requirements.health_check.check_type.value == "generic"
    assert requirements.health_check.send == "PING"
    assert requirements.health_check.expect == "PONG"
    assert requirements.health_check.db_user is None


def test_haproxy_route_tcp_requirements_health_check_with_type_mysql():
    """
    arrange: mock a charm with mysql health check type and db_user
    act: instantiate HaproxyRouteTcpRequirements
    assert: health check fields are correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 3306,
        "tcp-backend-port": 3306,
        "tcp-tls-terminate": False,
        "tcp-enforce-tls": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-health-check-interval": 5,
        "tcp-health-check-rise": 2,
        "tcp-health-check-fall": 3,
        "tcp-health-check-type": "mysql",
        "tcp-health-check-db-user": "health_checker",
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.health_check.check_type is not None
    assert requirements.health_check.check_type.value == "mysql"
    assert requirements.health_check.db_user == "health_checker"
    assert requirements.health_check.send is None
    assert requirements.health_check.expect is None


@pytest.mark.parametrize(
    "check_type",
    ["generic", "mysql", "postgres", "redis", "smtp"],
)
def test_haproxy_route_tcp_requirements_valid_health_check_types(check_type):
    """
    arrange: mock a charm with valid health check type
    act: instantiate HaproxyRouteTcpRequirements
    assert: health check type is correctly parsed
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-enforce-tls": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-health-check-interval": 10,
        "tcp-health-check-rise": 3,
        "tcp-health-check-fall": 5,
        "tcp-health-check-type": check_type,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.health_check.check_type is not None
    assert requirements.health_check.check_type.value == check_type


def test_haproxy_route_tcp_requirements_invalid_health_check_type():
    """
    arrange: mock a charm with invalid health check type
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-health-check-interval": 10,
        "tcp-health-check-rise": 3,
        "tcp-health-check-fall": 5,
        "tcp-health-check-type": "invalid_type",
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid health check type" in str(exc_info.value)



@pytest.mark.parametrize(
    "timeout_config,expected_server,expected_connect,expected_queue",
    [
        pytest.param(
            {
                "tcp-timeout-server": 10,
                "tcp-timeout-connect": 3,
                "tcp-timeout-queue": 5,
            },
            10,
            3,
            5,
            id="with_timeout",
        ),
        pytest.param({}, None, None, None, id="without_timeout"),
    ],
)
def test_haproxy_route_tcp_requirements_timeout_presence(
    timeout_config, expected_server, expected_connect, expected_queue
):
    """
    arrange: mock a charm with/without timeout configuration
    act: instantiate HaproxyRouteTcpRequirements
    assert: timeout values match expected
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
        **timeout_config,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.timeout.server == expected_server
    assert requirements.timeout.connect == expected_connect
    assert requirements.timeout.queue == expected_queue


@pytest.mark.parametrize(
    "invalid_value",
    [
        {"tcp-timeout-server": -1, "tcp-timeout-connect": 3, "tcp-timeout-queue": 5},
        {"tcp-timeout-server": 10, "tcp-timeout-connect": 0, "tcp-timeout-queue": 5},
        {"tcp-timeout-server": 10, "tcp-timeout-connect": 3, "tcp-timeout-queue": -5},
    ],
)
def test_haproxy_route_tcp_requirements_invalid_timeout_values(invalid_value):
    """
    arrange: mock a charm with invalid timeout values
    act: instantiate HaproxyRouteTcpRequirements
    assert: InvalidHaproxyRouteTcpRequirementsError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.1",
        "tcp-frontend-port": 443,
        "tcp-backend-port": 8443,
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        **invalid_value,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError) as exc_info:
        _make_tcp_integrator_state(charm)
    assert "Invalid haproxy-route-tcp configuration" in str(exc_info.value)


def test_haproxy_route_tcp_requirements_proxy_protocol_enabled():
    """
    arrange: mock a charm with tcp-enable-proxy-protocol set to True
    act: instantiate HaproxyRouteTcpRequirements
    assert: proxy_protocol is True
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "192.168.1.10",
        "tcp-frontend-port": 8443,
        "tcp-backend-port": 443,
        "tcp-tls-terminate": True,
        "tcp-hostname": "example.com",
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
        "tcp-enable-proxy-protocol": True,
    }

    requirements = _make_tcp_integrator_state(charm)

    assert requirements.proxy_protocol is True



# ---------------------------------------------------------------------------
# HaproxyRouteTcpState with port_mapping tests
# ---------------------------------------------------------------------------

BASE_PORT_MAPPING_CONFIG = {
    "tcp-backend-addresses": "10.0.0.1",
    "tcp-tls-terminate": True,
    "tcp-hostname": None,
    "tcp-load-balancing-algorithm": "leastconn",
    "tcp-load-balancing-consistent-hashing": False,
    "tcp-enforce-tls": True,
}


def test_haproxy_route_tcp_port_mapping_integrator_mode():
    """
    arrange: mock a charm with tcp-port-mapping set and no single-port config
    act: build HaproxyRouteTcpState for integrator mode
    assert: port_mapping is set, port and backend_port are None, frontend_start is correct
    """
    charm = Mock(CharmBase)
    charm.config = {
        **BASE_PORT_MAPPING_CONFIG,
        "tcp-port-mapping": "4000-4499:20000-20499",
    }

    state = _make_tcp_integrator_state(charm)

    assert state.port_mapping is not None
    assert isinstance(state.port_mapping, PortMapping)
    assert state.port_mapping.frontend.start == 4000
    assert state.port_mapping.frontend.end == 4499
    assert state.port_mapping.backend.start == 20000
    assert state.port_mapping.backend.end == 20499


def test_haproxy_route_tcp_port_mapping_mutually_exclusive_with_frontend_port():
    """
    arrange: mock a charm with both tcp-port-mapping and tcp-frontend-port set
    act: build HaproxyRouteTcpState for integrator mode
    assert: InvalidHaproxyRouteTcpStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        **BASE_PORT_MAPPING_CONFIG,
        "tcp-port-mapping": "4000-4499:20000-20499",
        "tcp-frontend-port": 4000,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError, match="mutually exclusive"):
        _make_tcp_integrator_state(charm)


def test_haproxy_route_tcp_port_mapping_mutually_exclusive_with_backend_port():
    """
    arrange: mock a charm with both tcp-port-mapping and tcp-backend-port set (no frontend port)
    act: build HaproxyRouteTcpState for integrator mode
    assert: InvalidHaproxyRouteTcpStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        **BASE_PORT_MAPPING_CONFIG,
        "tcp-port-mapping": "4000-4499:20000-20499",
        "tcp-backend-port": 20000,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError, match="mutually exclusive"):
        _make_tcp_integrator_state(charm)


def test_haproxy_route_tcp_port_mapping_invalid_mapping_string():
    """
    arrange: mock a charm with an unparseable tcp-port-mapping value
    act: build HaproxyRouteTcpState for integrator mode
    assert: InvalidHaproxyRouteTcpStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        **BASE_PORT_MAPPING_CONFIG,
        "tcp-port-mapping": "not-valid",
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError, match="Invalid tcp-port-mapping"):
        _make_tcp_integrator_state(charm)


def test_haproxy_route_tcp_port_mapping_unequal_ranges_via_integrator_mode():
    """
    arrange: mock a charm with tcp-port-mapping with unequal frontend/backend range sizes
    act: call build_for_integrator_mode
    assert: InvalidHaproxyRouteTcpStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-backend-addresses": "10.0.0.1",
        "tcp-port-mapping": "4000-4499:20000-20099",  # 500 frontend vs 100 backend
        "tcp-tls-terminate": True,
        "tcp-hostname": None,
        "tcp-load-balancing-algorithm": "leastconn",
        "tcp-load-balancing-consistent-hashing": False,
        "tcp-enforce-tls": True,
    }

    with pytest.raises(InvalidHaproxyRouteTcpStateError):
        HaproxyRouteTcpState.build_for_integrator_mode(charm)


def test_has_integrator_config_with_port_mapping():
    """
    arrange: mock a charm with only tcp-port-mapping config set
    act: call HaproxyRouteTcpState.has_integrator_config
    assert: returns True
    """
    charm = Mock(CharmBase)
    charm.config = {
        "tcp-port-mapping": "4000-4499:20000-20499",
    }

    assert HaproxyRouteTcpState.has_integrator_config(charm) is True
