# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Kubernetes model fixtures for integration tests."""

import logging

import jubilant
import pytest

from ..conftest import JUJU_WAIT_TIMEOUT

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="juju")
def juju_model_fixture(request: pytest.FixtureRequest):
    """Create a temporary model on the active Kubernetes controller."""
    keep_models = bool(request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju

        if request.session.testsfailed:
            logger.error(juju.debug_log(limit=1000))


@pytest.fixture(scope="module", name="juju_k8s")
def juju_k8s_fixture(juju: jubilant.Juju) -> jubilant.Juju:
    """Expose the Kubernetes model under the existing fixture name."""
    return juju
