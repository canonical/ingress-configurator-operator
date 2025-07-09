# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress-configurator charm."""

import logging

import ops.testing

logger = logging.getLogger(__name__)


def test_config_changed(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run start
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    out = context.run(context.on.config_changed(), state)
    assert out.unit_status == ops.testing.BlockedStatus(
        "Missing configuration for integrator mode: backend-addresses backend-ports"
    )


def test_config_changed_invalid_address(context, base_state):
    """
    arrange: prepare some state with peer relation.
    act: run start with invalid backend_address configuration.
    assert: status is active.
    """
    state = ops.testing.State(
        **base_state, config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080"}
    )
    out = context.run(context.on.config_changed(), state)
    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_addresses-1"
    )


def test_config_changed_invalid_port(context, base_state):
    """
    arrange: prepare some state with peer relation.
    act: run start with invalid port configuration.
    assert: status is blocked with the correct message.
    """
    state = ops.testing.State(
        **base_state, config={"backend-addresses": "10.0.0.1,10.0.0.2", "backend-ports": "99999"}
    )
    out = context.run(context.on.config_changed(), state)
    assert out.unit_status == ops.testing.BlockedStatus(
        "Invalid integrator configuration: backend_ports-0"
    )
