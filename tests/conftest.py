# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""


def pytest_addoption(parser):
    """Add integration test command-line options."""
    parser.addoption("--keep-models", action="store_true", default=False)


def pytest_configure(config):
    """Adds config options.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line("markers", "abort_on_fail")
