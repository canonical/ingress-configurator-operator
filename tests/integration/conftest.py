# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests configuration."""

import json
import pathlib
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Callable, cast

import jubilant
import pytest
import yaml
from requests import Session

from .helper import DNSResolverHTTPSAdapter

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"
HAPROXY_HTTP_REQUIRER_SRC = "tests/integration/any_charm_http_requirer.py"
HAPROXY_INGRESS_REQUIRER_SRC = "tests/integration/any_charm_ingress_requirer.py"
HELPER_SRC = "tests/integration/helper.py"
INGRESS_LIB_SRC = "lib/charms/traefik_k8s/v2/ingress.py"
APT_LIB_SRC = "lib/charms/operator_libs_linux/v0/apt.py"
JUJU_WAIT_TIMEOUT = 10 * 60  # 10 minutes
HAPROXY_APP_NAME = "haproxy"
HAPROXY_CHANNEL = "2.8/edge"
HAPROXY_REVISION = 194
HAPROXY_BASE = "ubuntu@24.04"
CERTIFICATES_APP_NAME = "self-signed-certificates"
CERTIFICATES_CHANNEL = "1/stable"
CERTIFICATES_REVISION = 263
ANY_CHARM_APP_NAME = "any-charm-backend"
INGRESS_REQUIRER_APP_NAME = "ingress-requirer"


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

    model = request.config.getoption("--model")
    if model:
        juju = jubilant.Juju(model=model)
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju
        show_debug_log(juju)
        return

    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju


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
    if pytestconfig.getoption("--no-setup") and app_name in juju.status().apps:
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
    if pytestconfig.getoption("--no-setup") and HAPROXY_APP_NAME in juju.status().apps:
        yield HAPROXY_APP_NAME
        return
    juju.deploy(
        charm="haproxy",
        app=HAPROXY_APP_NAME,
        channel=HAPROXY_CHANNEL,
        revision=HAPROXY_REVISION,
        config={"external-hostname": MOCK_HAPROXY_HOSTNAME},
        base=HAPROXY_BASE,
    )
    juju.deploy(
        charm="self-signed-certificates",
        app=CERTIFICATES_APP_NAME,
        channel=CERTIFICATES_CHANNEL,
        revision=CERTIFICATES_REVISION,
    )
    juju.integrate(f"{CERTIFICATES_APP_NAME}:certificates", f"{HAPROXY_APP_NAME}:certificates")
    juju.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, CERTIFICATES_APP_NAME),
    )
    yield HAPROXY_APP_NAME


@pytest.fixture(scope="module", name="any_charm_backend")
def any_charm_backend_fixture(pytestconfig: pytest.Config, juju: jubilant.Juju):
    """Deploy any-charm and configure it to serve as a requirer for the http interface."""
    if pytestconfig.getoption("--no-setup") and ANY_CHARM_APP_NAME in juju.status().apps:
        yield ANY_CHARM_APP_NAME
        return
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=ANY_CHARM_APP_NAME,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": pathlib.Path(HAPROXY_HTTP_REQUIRER_SRC).read_text(
                        encoding="utf-8"
                    )
                }
            ),
        },
        num_units=2,
    )
    juju.wait(
        lambda status: jubilant.all_active(status, ANY_CHARM_APP_NAME, CERTIFICATES_APP_NAME)
    )
    for unit in juju.status().apps[ANY_CHARM_APP_NAME].units.keys():
        juju.run(unit, "rpc", {"method": "start_server"})
    juju.wait(lambda status: jubilant.all_active(status, ANY_CHARM_APP_NAME))
    yield ANY_CHARM_APP_NAME


@pytest.fixture(scope="module")
def http_session() -> Callable[[list[tuple[str, IPv4Address | IPv6Address]]], Session]:
    """Create a requests session with custom DNS resolution."""

    def _make_session(dns_entries: list[tuple[str, IPv4Address | IPv6Address]]) -> Session:
        """Create a requests session with custom DNS resolution."""
        session = Session()
        for hostname, address in dns_entries:
            session.mount(
                f"https://{hostname}",
                DNSResolverHTTPSAdapter(hostname, str(address)),
            )
        return session

    return _make_session


@pytest.fixture(scope="module", name="ingress_requirer")
def ingress_requirer_fixture(pytestconfig: pytest.Config, juju: jubilant.Juju, application: str):
    """Deploy and configure any-charm to serve as an ingress requirer for the ingress interface."""
    if pytestconfig.getoption("--no-setup") and INGRESS_REQUIRER_APP_NAME in juju.status().apps:
        yield INGRESS_REQUIRER_APP_NAME
        return
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=INGRESS_REQUIRER_APP_NAME,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": pathlib.Path(HAPROXY_INGRESS_REQUIRER_SRC).read_text(
                        encoding="utf-8"
                    ),
                    "ingress.py": pathlib.Path(INGRESS_LIB_SRC).read_text(encoding="utf-8"),
                }
            ),
            "python-packages": "pydantic",
        },
    )
    juju.wait(
        lambda status: jubilant.all_active(
            status, INGRESS_REQUIRER_APP_NAME, "self-signed-certificates"
        )
    )
    for unit in juju.status().apps[INGRESS_REQUIRER_APP_NAME].units.keys():
        juju.run(unit, "rpc", {"method": "start_server"})
    juju.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{application}:ingress")
    juju.wait(lambda status: jubilant.all_active(status, INGRESS_REQUIRER_APP_NAME))
    yield INGRESS_REQUIRER_APP_NAME


def get_unit_addresses(juju: jubilant.Juju, application: str) -> list[IPv4Address | IPv6Address]:
    """Fetch all unit addresses from juju status.

    Args:
        juju: jubilant Juju class.
        application: Name of the application

    Returns:
        The list of addresses of all the units of the application.
    """
    unit_addresses: list[IPv4Address | IPv6Address] = []
    if application_status := juju.status().apps.get(application):
        for unit_status in application_status.units.values():
            unit_addresses.append(ip_address(unit_status.public_address))
    return unit_addresses
