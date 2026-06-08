# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state.kubernetes."""

import pytest
from pydantic import ValidationError

from state.kubernetes import NodePortState


def test_nodeport_state_invalid_port():
    """
    arrange: construct a NodePortState with an out-of-range nodePort
    act: instantiate NodePortState
    assert: ValidationError is raised
    """
    with pytest.raises(ValidationError):
        NodePortState(
            backend_addresses=["10.0.0.1"],
            service_name="my-service",
            backend_port=99999,
        )
