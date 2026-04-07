# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")
    # --keep-models is passed by reusable CI workflows
    # It's consumed as a no-op here to avoid "unrecognized arguments" errors.
    # pytest-jubilant v2 uses --no-juju-teardown instead.
    parser.addoption("--keep-models", action="store_true", default=False)
