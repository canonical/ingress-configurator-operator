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
    act: trigger a config changed event.
    assert: status is blocked.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": ",127.0.0.1,127.0.0.2", "backend-ports": "8080,8081"}
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("Missing haproxy-route relation.")


def test_config_changed_invalid_state(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state with invalid backend-addresses.
    act: trigger a config changed event.
    assert: status is bllocked.
    """
    monkeypatch.setattr(state.State, "from_charm", MagicMock(side_effect=state.InvalidStateError))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus()
