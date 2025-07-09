# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Integration tests configuration."""

import ipaddress
import json
import pathlib
from typing import cast

import jubilant
import pytest
import yaml
from requests import Session

from .helper import DNSResolverHTTPSAdapter

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"
INGRESS_REQUIRER_SRC = "tests/integration/any_charm_requirer.py"
APT_LIB_SRC = "lib/charms/operator_libs_linux/v0/apt.py"


@pytest.fixture(scope="session", name="charm")
def charm_fixture(pytestconfig: pytest.Config):
    """Pytest fixture that packs the charm and returns the filename, or --charm-file if set."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "--charm-file must be set"
    yield charm


@pytest.fixture(scope="module", name="juju")
def juju_fixture(request: pytest.FixtureRequest):
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""

    def show_debug_log(juju: jubilant.Juju):
        """Show the debug log if tests failed.

        Args:
            juju: Jubilant juju instance.
        """
        if request.session.testsfailed:
            log = juju.debug_log(limit=1000)
            print(log, end="")

    use_existing = request.config.getoption("--use-existing", default=False)
    if use_existing:
        juju = jubilant.Juju()
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return

    model = request.config.getoption("--model")
    if model:
        juju = jubilant.Juju(model=model)
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return

    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return


@pytest.fixture(scope="module", name="application")
def application_fixture(pytestconfig: pytest.Config, juju: jubilant.Juju, charm: str):
    """Deploy the ingress-configurator application.

    Args:
        juju: Jubilant juju fixture.
        charm_file: Path to the packed charm file.

    Yields:
        The ingress-configurator app name.
    """
    metadata = yaml.safe_load(pathlib.Path("./charmcraft.yaml").read_text(encoding="UTF-8"))
    app_name = metadata["name"]
    if pytestconfig.getoption("--no-deploy") and app_name in juju.status().apps:
        yield app_name
        return
    juju.deploy(
        charm=charm,
        app=app_name,
        base="ubuntu@24.04",
    )
    yield app_name


@pytest.fixture(scope="module", name="haproxy")
def haproxy_fixture(pytestconfig: pytest.Config, juju: jubilant.Juju):
    """_summary_

    Args:
        juju: Jubilant juju fixture.

    Yields:
        The haproxy app name.
    """
    haproxy_app_name = "haproxy"
    if pytestconfig.getoption("--no-deploy") and haproxy_app_name in juju.status().apps:
        yield haproxy_app_name
        return
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
        lambda status: jubilant.all_active(status, haproxy_app_name, "self-signed-certificates"),
    )
    yield haproxy_app_name


@pytest.fixture(scope="module", name="ingress_requirer")
def ingress_requirer_fixture(pytestconfig: pytest.Config, juju: jubilant.Juju):
    """Deploy any-charm and configure it to serve as a requirer for the http interface."""
    app_name = "ingress-requirer"
    if pytestconfig.getoption("--no-deploy") and app_name in juju.status().apps:
        yield app_name
        return
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=app_name,
        config={
            "src-overwrite": json.dumps(
                {"any_charm.py": pathlib.Path(INGRESS_REQUIRER_SRC).read_text(encoding="utf-8")}
            ),
        },
    )
    juju.wait(lambda status: jubilant.all_active(status, app_name, "self-signed-certificates"))
    juju.run(f"{app_name}/0", "rpc", {"method": "start_server"})
    yield app_name


@pytest.fixture(scope="module", name="session")
def modified_session_fixture(juju: jubilant.Juju):
    """Fixture to provide a session with a custom HTTPS adapter."""
    haproxy_app = juju.status().apps["haproxy"]
    _, haproxy_unit = next(iter(haproxy_app.units.items()))
    haproxy_address = ipaddress.ip_address(haproxy_unit.public_address)

    session = Session()
    session.mount(
        "https://",
        DNSResolverHTTPSAdapter(MOCK_HAPROXY_HOSTNAME, str(haproxy_address)),
    )
    yield session
