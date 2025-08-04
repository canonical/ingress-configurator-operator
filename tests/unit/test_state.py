# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the configurator module."""

from unittest.mock import Mock

import pytest
from charms.traefik_k8s.v2.ingress import (
    IngressRequirerAppData,
    IngressRequirerData,
    IngressRequirerUnitData,
)
from ops import CharmBase

import state


def test_adapter_state_from_charm():
    """
    arrange: mock a charm with an ingress relation
    act: instantiate a State
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "health-check-interval": 20,
        "health-check-rise": 3,
        "health-check-fall": 4,
        "health-check-path": "/health",
        "health-check-port": 8080,
        "retry-count": 1,
        "retry-redispatch": True,
        "timeout-server": 11,
        "timeout-connect": 12,
        "timeout-queue": 13,
        "paths": "/api/v1,/api/v2",
        "hostname": "api.example.com",
        "additional-hostnames": "api2.example.com,api3.example.com",
    }
    ingress_relation_data = IngressRequirerData(
        app=IngressRequirerAppData(model="model", name="name", port=8080),
        units=[IngressRequirerUnitData(host="sample.host", ip="127.0.0.1")],
    )
    charm_state = state.State.from_charm(charm, ingress_relation_data)

    assert [str(address) for address in charm_state.backend_addresses] == [
        ingress_relation_data.units[0].ip
    ]
    assert charm_state.backend_ports == [ingress_relation_data.app.port]
    assert charm_state.backend_protocol == "http"
    assert charm_state.health_check.interval == charm.config.get("health-check-interval")
    assert charm_state.health_check.rise == charm.config.get("health-check-rise")
    assert charm_state.health_check.fall == charm.config.get("health-check-fall")
    assert charm_state.health_check.path == charm.config.get("health-check-path")
    assert charm_state.health_check.port == charm.config.get("health-check-port")
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.redispatch == charm.config.get("retry-redispatch")
    assert charm_state.timeout.server == charm.config.get("timeout-server")
    assert charm_state.timeout.connect == charm.config.get("timeout-connect")
    assert charm_state.timeout.queue == charm.config.get("timeout-queue")
    assert charm_state.paths == charm.config.get("paths").split(",")
    assert charm_state.hostname == charm.config.get("hostname")
    assert charm_state.additional_hostnames == charm.config.get("additional-hostnames").split(",")


def test_integrator_state_from_charm():
    """
    arrange: mock a charm with backend configuration
    act: instantiate a State
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "retry-count": 1,
        "retry-redispatch": True,
    }
    charm_state = state.State.from_charm(charm, None)
    assert [str(address) for address in charm_state.backend_addresses] == charm.config.get(
        "backend-addresses"
    ).split(",")
    assert [str(port) for port in charm_state.backend_ports] == charm.config.get(
        "backend-ports"
    ).split(",")
    assert charm_state.backend_protocol == "http"
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.redispatch == charm.config.get("retry-redispatch")


def test_state_from_charm_no_backend():
    """
    arrange: mock a charm with backend address and without backend configuration not ingress
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {}
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_address():
    """
    arrange: mock a charm with backend port and without address configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "invalid",
        "backend-ports": "8080",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_paths():
    """
    arrange: mock a charm with backend addresses, ports configuration and invalid paths
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "paths": "invalid path",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_port():
    """
    arrange: mock a charm with backend address and invalid port configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "99999",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_protocol():
    """Check that backend-protocol config field is validated."""
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "80",
        "backend-protocol": "gopher",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_path():
    """
    arrange: mock a charm with backend address and invalid health-check-path configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-path": "invalid$path",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_port():
    """
    arrange: mock a charm with backend address and invalid health-check-port configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-port": 99999,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_interval():
    """
    arrange: mock a charm with backend address and invalid health-check-interval configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-interval": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_rise():
    """
    arrange: mock a charm with backend address and invalid health-check-rise configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-rise": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_fall():
    """
    arrange: mock a charm with backend address and invalid health-check-fall configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-fall": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_missing_check_interval():
    """
    arrange: mock a charm with backend address and unset health-check-interval configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-rise": 3,
        "health-check-fall": 4,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_missing_check_rise():
    """
    arrange: mock a charm with backend address and unset health-check-rise configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-interval": 20,
        "health-check-fall": 4,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_missing_check_fall():
    """
    arrange: mock a charm with backend address and unset health-check-fall configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "health-check-interval": 20,
        "health-check-rise": 3,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_retry_count():
    """
    arrange: mock a charm with backend address and invalid retry-count configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "retry-count": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_timeout_server():
    """
    arrange: mock a charm with backend address and invalid timeout-server configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-server": -1,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_timeout_connect():
    """
    arrange: mock a charm with backend address and invalid timeout-connect configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-connect": -1,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_timeout_queue():
    """
    arrange: mock a charm with backend address and invalid timeout-queue configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080",
        "timeout-queue": -1,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_hostname():
    """
    arrange: mock a charm with backend addresses, ports configuration and invalid hostname
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "hostname": "invalid$hostname",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_additional_hostnames():
    """
    arrange: mock a charm with invalid additional-hostnames config
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "hostname": "valid.example.com",
        "additional-hostnames": "invalid$\\",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_port_invalid_int():
    """
    arrange: mock a charm with invalid port config (not an integer)
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "invalid",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)
