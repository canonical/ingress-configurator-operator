# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for architecture-specific integration test configuration."""

import pytest

from tests.integration.helper import ArchitectureRevisions, architecture_revision


@pytest.mark.parametrize(
    ("architecture", "expected_revision"),
    (("amd64", 185), ("arm64", 186)),
)
def test_architecture_revision(architecture: str, expected_revision: int):
    """Select the revision matching the requested architecture."""
    revisions = ArchitectureRevisions(amd64=185, arm64=186)
    assert architecture_revision(revisions, architecture) == expected_revision


def test_architecture_revision_rejects_unsupported_architecture():
    """Fail explicitly when no revision is published for the architecture."""
    with pytest.raises(ValueError, match="unsupported architecture: s390x"):
        architecture_revision(ArchitectureRevisions(amd64=185, arm64=186), "s390x")
