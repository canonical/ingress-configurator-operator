# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")
    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="Keep temporary models created by the tests instead of tearing them down.",
    )
    parser.addoption(
        "--gateway-class",
        action="store",
        default=None,
        help="GatewayClass to configure on gateway-api-integrator (default: cilium).",
    )


def pytest_configure(config):
    """Adds config options.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line("markers", "abort_on_fail")
