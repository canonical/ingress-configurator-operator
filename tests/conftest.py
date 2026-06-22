# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")


def pytest_configure(config):
    """Adds config options.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line("markers", "abort_on_fail")
