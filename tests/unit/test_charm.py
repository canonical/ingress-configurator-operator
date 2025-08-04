# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

from unittest.mock import ANY, MagicMock

import ops.testing
import pytest

import state


def test_config_changed_no_haproxy_route_relation(context):
    """
    arrange: prepare some valid state without haproxy-route relation.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": ",127.0.0.1,127.0.0.2", "backend-ports": "8080,8081"},
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("Missing haproxy-route relation.")


def test_config_changed_invalid_state(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state with invalid backend-addresses.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    monkeypatch.setattr(state.State, "from_charm", MagicMock(side_effect=state.InvalidStateError))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus()


def test_config_changed_integrator(context):
    """
    arrange: prepare some valid state for an integrator.
    act: trigger a config changed event.
    assert: status is active.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,10.0.0.2", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.ActiveStatus()


def test_protocol_propagated_to_haproxy(context: ops.testing.Context):
    """Valid protocol should be copied from config to haproxy-route relation"""
    in_ = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "80",
            "backend-protocol": "https",
        },
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )
    out = context.run(context.on.config_changed(), in_)

    assert out.unit_status == ops.testing.ActiveStatus("")
    assert out.get_relations("haproxy-route")[0].local_app_data == {
        "service": ANY,
        "ports": "[80]",
        "hosts": '["10.0.0.1"]',
        "protocol": '"https"',
    }
