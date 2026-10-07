# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""LXD model fixtures for integration tests."""

import logging

import jubilant
import pytest

from ..conftest import JUJU_WAIT_TIMEOUT

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="juju_lxd")
def juju_lxd_fixture(request: pytest.FixtureRequest):
    """Create a temporary model on the Concierge LXD controller."""
    keep_models = bool(request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models, controller="concierge-lxd") as juju:
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju

        if request.session.testsfailed:
            logger.error(juju.debug_log(limit=1000))
