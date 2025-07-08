# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

from unittest.mock import MagicMock

import ops.testing
import pytest

from state import configurator


def test_config_changed_no_haproxy_route_relation(context):
    """
    arrange: prepare some valid state without haproxy-route relation.
    act: run start.
    assert: status is blocked.
    """
    state = ops.testing.State(config={"backend_address": "127.0.0.2", "backend_port": 8080})

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus("Missing haproxy-route relation.")


def test_config_changed_invalid_mode(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state and patch invalid mode.
    act: run start.
    assert: status is blocked.
    """
    monkeypatch.setattr(
        configurator, "get_mode", MagicMock(side_effect=configurator.UndefinedModeError)
    )
    state = ops.testing.State(
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus("Mode is invalid.")


def test_config_changed(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state with haproxy-route relation.
    act: run start.
    assert: status is active.
    """
    monkeypatch.setattr(
        configurator, "get_mode", MagicMock(return_value=configurator.Mode.INTEGRATOR)
    )
    state = ops.testing.State(
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        (
            "Missing configuration for integrator mode, "
            "both backend_port and backend_address must be set."
        )
    )


def test_config_changed_invalid_address(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state.
    act: run start with invalid backend_address configuration.
    assert: status is active.
    """
    monkeypatch.setattr(
        configurator, "get_mode", MagicMock(return_value=configurator.Mode.INTEGRATOR)
    )
    state = ops.testing.State(
        config={"backend_address": "invalid", "backend_port": 8080},
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_address"
    )


def test_config_changed_invalid_port(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state.
    act: run start with invalid port configuration.
    assert: status is blocked with the correct message.
    """
    monkeypatch.setattr(
        configurator, "get_mode", MagicMock(return_value=configurator.Mode.INTEGRATOR)
    )
    state = ops.testing.State(
        config={"backend_address": "10.0.0.1", "backend_port": 99999},
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_port"
    )
