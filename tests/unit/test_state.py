# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the configurator module."""

from unittest.mock import Mock

import pytest
from ops import CharmBase, Relation

import state


def test_get_mode_integrator():
    """
    arrange: mock a charm with backend configuration
    act: get mode
    assert: mode is 'integrator'
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
    }
    assert state.Mode.INTEGRATOR == state.get_mode(charm, None)


def test_get_mode_adapter():
    """
    arrange: mock a charm without backend configuration and a relation
    act: get mode
    assert: mode is 'adapter'
    """
    charm = Mock(CharmBase)
    charm.config = {}
    relation = Mock(Relation)
    assert state.Mode.ADAPTER == state.get_mode(charm, relation)


def test_get_mode_invalid():
    """
    arrange: mock a charm with backend configuration and a relation
    act: get mode
    assert: a UndefinedModeError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
        "backend-ports": "8080,8081",
    }
    relation = Mock(Relation)
    with pytest.raises(state.UndefinedModeError):
        state.get_mode(charm, relation)


def test_get_integrator_information():
    """
    arrange: mock a charm with backend configuration
    act: instantiate a IntegratorInformation
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
    info = state.IntegratorInformation.from_charm(charm)
    assert [str(address) for address in info.backend_addresses] == charm.config.get(
        "backend-addresses"
    ).split(",")
    assert [str(port) for port in info.backend_ports] == charm.config.get("backend-ports").split(
        ","
    )
    assert info.retry_count == charm.config.get("retry-count")
    assert info.retry_interval == charm.config.get("retry-interval")
    assert info.retry_redispatch == charm.config.get("retry-redispatch")


def test_get_integrator_information_no_address():
    """
    arrange: mock a charm with backend port and without address configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-ports": "8080,8081",
    }
    with pytest.raises(state.InvalidIntegratorConfigError):
        state.IntegratorInformation.from_charm(charm)


def test_get_integrator_information_no_port():
    """
    arrange: mock a charm with backend address and without port configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1,127.0.0.2",
    }
    with pytest.raises(state.InvalidIntegratorConfigError):
        state.IntegratorInformation.from_charm(charm)


def test_get_integrator_information_invalid_retry_count():
    """
    arrange: mock a charm with backend address and without retry-count configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "retry-count": -1,
    }
    with pytest.raises(state.InvalidIntegratorConfigError):
        state.IntegratorInformation.from_charm(charm)


def test_get_integrator_information_invalid_retry_interval():
    """
    arrange: mock a charm with backend address and without retry-interval configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "retry-interval": -1,
    }
    with pytest.raises(state.InvalidIntegratorConfigError):
        state.IntegratorInformation.from_charm(charm)
