# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the configurator module."""

from unittest.mock import Mock

import pytest
from ops import CharmBase, Relation

from state import configurator


def test_get_mode_integrator():
    """
    arrange: mock a charm with backend configuration
    act: get mode
    assert: mode is 'integrator'
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend_address": "127.0.0.2",
        "backend_port": "8080",
    }
    assert configurator.Mode.INTEGRATOR == configurator.get_mode(charm, None)


def test_get_mode_adapter():
    """
    arrange: mock a charm without backend configuration and a relation
    act: get mode
    assert: mode is 'adapter'
    """
    charm = Mock(CharmBase)
    charm.config = {}
    relation = Mock(Relation)
    assert configurator.Mode.ADAPTER == configurator.get_mode(charm, relation)


def test_get_mode_invalid():
    """
    arrange: mock a charm with backend configuration and a relation
    act: get mode
    assert: a UndefinedModeError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend_address": "127.0.0.2",
        "backend_port": "8080",
    }
    relation = Mock(Relation)
    with pytest.raises(configurator.UndefinedModeError):
        configurator.get_mode(charm, relation)


def test_get_integrator_information():
    """
    arrange: mock a charm with backend configuration
    act: instantiate a IntegratorInformation
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend_address": "127.0.0.2",
        "backend_port": "8080",
    }
    info = configurator.IntegratorInformation.from_charm(charm)
    assert str(info.backend_address) == charm.config.get("backend_address")
    assert str(info.backend_port) == charm.config.get("backend_port")


def test_get_integrator_information_no_address():
    """
    arrange: mock a charm with backend port and without address configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend_port": "8080",
    }
    with pytest.raises(configurator.InvalidIntegratorConfigError):
        configurator.IntegratorInformation.from_charm(charm)


def test_get_integrator_information_no_port():
    """
    arrange: mock a charm with backend address and without port configuration
    act: instantiate a IntegratorInformation
    assert: a InvalidIntegratorConfigError is raised
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend_address": "127.0.0.2",
    }
    with pytest.raises(configurator.InvalidIntegratorConfigError):
        configurator.IntegratorInformation.from_charm(charm)
