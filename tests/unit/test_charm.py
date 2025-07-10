# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

from unittest.mock import MagicMock

import ops.testing
import pytest

import state


def test_config_changed_no_haproxy_route_relation(context):
    """
    arrange: prepare some valid state without haproxy-route relation.
    act: run start.
    assert: status is blocked.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": ",127.0.0.1,127.0.0.2", "backend-ports": "8080,8081"}
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("Missing haproxy-route relation.")


def test_config_changed_invalid_mode(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state and patch invalid mode.
    act: run start.
    assert: status is blocked.
    """
    monkeypatch.setattr(state, "get_mode", MagicMock(side_effect=state.UndefinedModeError))
    charm_state = ops.testing.State(
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("Mode is invalid.")


def test_config_changed(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state with haproxy-route relation.
    act: run start.
    assert: status is active.
    """
    monkeypatch.setattr(state, "get_mode", MagicMock(return_value=state.Mode.INTEGRATOR))
    charm_state = ops.testing.State(
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Missing configuration for integrator mode: backend-addresses backend-ports"
    )


def test_config_changed_invalid_address(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state.
    act: run start with invalid backend_address configuration.
    assert: status is active.
    """
    monkeypatch.setattr(state, "get_mode", MagicMock(return_value=state.Mode.INTEGRATOR))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_addresses-1"
    )


def test_config_changed_invalid_port(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state.
    act: run start with invalid port configuration.
    assert: status is blocked with the correct message.
    """
    monkeypatch.setattr(state, "get_mode", MagicMock(return_value=state.Mode.INTEGRATOR))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,10.0.0.2", "backend-ports": "99999"},
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_ports-0"
    )
