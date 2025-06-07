# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Integration tests configuration."""

import pathlib

import jubilant
import pytest
import yaml

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"


@pytest.fixture(scope="session", name="charm")
def charm_fixture(pytestconfig: pytest.Config):
    """Pytest fixture that packs the charm and returns the filename, or --charm-file if set."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "--charm-file must be set"
    yield charm


@pytest.fixture(scope="module", name="juju")
def juju_fixture():
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""
    with jubilant.temp_model() as juju:
        yield juju


@pytest.fixture(scope="module", name="application")
def application_fixture(juju: jubilant.Juju, charm: str):
    """Deploy the ingress-configurator application.

    Args:
        juju: Jubilant juju fixture.
        charm_file: Path to the packed charm file.

    Yields:
        The ingress-configurator app name.
    """
    metadata = yaml.safe_load(pathlib.Path("./charmcraft.yaml").read_text(encoding="UTF-8"))
    app_name = metadata["name"]
    juju.deploy(
        charm=charm,
        app=app_name,
        base="ubuntu@24.04",
    )
    yield app_name


@pytest.fixture(scope="module", name="haproxy")
def haproxy_fixture(juju: jubilant.Juju):
    """_summary_

    Args:
        juju: Jubilant juju fixture.

    Yields:
        The haproxy app name.
    """
    haproxy_app_name = "haproxy"
    juju.deploy(
        charm="haproxy",
        app=haproxy_app_name,
        channel="2.8/edge",
        revision=158,
        config={"external-hostname": MOCK_HAPROXY_HOSTNAME},
        base="ubuntu@24.04",
    )
    juju.deploy(charm="self-signed-certificates", channel="1/stable", revision=263)
    juju.integrate("self-signed-certificates:certificates", f"{haproxy_app_name}:certificates")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy_app_name, "self-signed-certificates")
    )
    yield haproxy_app_name
