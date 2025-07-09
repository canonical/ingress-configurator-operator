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
        help="keep temporarily-created models",
    )
    parser.addoption(
        "--model",
        action="store",
        help="Juju model to use; if not provided, a new model "
        "will be created for each test which requires one",
    )
    parser.addoption(
        "--no-deploy",
        action="store_true",
        default=False,
        help="do not deploy the charm, assume it is already deployed",
    )


def pytest_configure(config):
    """Adds config options.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line("markers", "abort_on_fail")
