# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,missing-function-docstring
"""Unit tests."""

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from ops.testing import Context

from charm import IngressConfiguratorCharm

if TYPE_CHECKING:
    from lightkube import Client as LightkubeClient


@pytest.fixture(name="context_machine")
def context_machine_fixture() -> Generator[Context[IngressConfiguratorCharm], None, None]:
    """Context fixture.

    Yield: The charm context.
    """
    yield Context(charm_type=IngressConfiguratorCharm, machine_id="0")


@pytest.fixture(name="context_k8s")
def context_k8s_fixture() -> Generator[Context[IngressConfiguratorCharm], None, None]:
    """Context fixture for gateway-route tests (Kubernetes substrate)."""
    yield Context(charm_type=IngressConfiguratorCharm, machine_id=None)


@pytest.fixture(name="mock_lightkube")
def mock_lightkube_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator["LightkubeClient", None, None]:
    """Mock lightkube Client to avoid K8s API calls."""
    mock_client = MagicMock()
    mock_client.list.return_value = []
    monkeypatch.setattr("charm.Client", MagicMock(return_value=mock_client))
    yield mock_client
