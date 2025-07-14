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
        "check-interval": 20,
        "check-rise": 3,
        "check-fall": 4,
        "check-path": "/health",
        "check-port": 8080,
        "retry-count": 1,
        "retry-interval": 10,
        "retry-redispatch": True,
        "paths": "/api/v1,/api/v2",
        "subdomains": "api",
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
    assert charm_state.check.interval == charm.config.get("check-interval")
    assert charm_state.check.rise == charm.config.get("check-rise")
    assert charm_state.check.fall == charm.config.get("check-fall")
    assert charm_state.check.path == charm.config.get("check-path")
    assert charm_state.check.port == charm.config.get("check-port")
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.interval == charm.config.get("retry-interval")
    assert charm_state.retry.redispatch == charm.config.get("retry-redispatch")
    assert charm_state.paths == charm.config.get("paths").split(",")
    assert charm_state.subdomains == charm.config.get("subdomains").split(",")


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
        "retry-interval": 10,
        "retry-redispatch": True,
    }
    charm_state = state.State.from_charm(charm, None)
    assert [str(address) for address in charm_state.backend_addresses] == charm.config.get(
        "backend-addresses"
    ).split(",")
    assert [str(port) for port in charm_state.backend_ports] == charm.config.get(
        "backend-ports"
    ).split(",")
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.interval == charm.config.get("retry-interval")
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
    arrange: mock a charm with backend address and without port configuration
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


def test_state_from_charm_invalid_check_path():
    """
    arrange: mock a charm with backend address and invalid check-path configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "check-path": "invalid$path",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_port():
    """
    arrange: mock a charm with backend address and invalid check-port configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "check-port": 99999,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_interval():
    """
    arrange: mock a charm with backend address and invalid check-interval configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "check-interval": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_rise():
    """
    arrange: mock a charm with backend address and invalid check-rise configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "check-rise": 0,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_check_fall():
    """
    arrange: mock a charm with backend address and invalid check-fall configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "check-fall": 0,
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


def test_state_from_charm_invalid_retry_interval():
    """
    arrange: mock a charm with backend address and invalid retry-interval configuration
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "retry-interval": -1,
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)


def test_state_from_charm_invalid_subdomains():
    """
    arrange: mock a charm with backend addresses, ports configuration and invalid subdomains
    act: instantiate a State
    assert: a InvalidStateError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
        "subdomains": "invalid$subdomains",
    }
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm, None)
