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
        (
            "Missing configuration for integrator mode, "
            "both backend_port and backend_address must be set."
        )
    )
