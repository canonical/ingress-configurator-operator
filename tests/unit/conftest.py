# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

# pylint: disable=duplicate-code,missing-function-docstring
"""Unit tests."""

import pytest
from ops.testing import Context

from charm import IngressConfiguratorCharm


@pytest.fixture(name="context")
def context_fixture():
    """Context fixture.

    Yield: The charm context.
    """
    yield Context(charm_type=IngressConfiguratorCharm)
