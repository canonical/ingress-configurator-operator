# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests configuration."""

import json
import pathlib
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Callable, Generator, cast

import jubilant
import pytest
import yaml
from requests import Session

from .helper import DNSResolverAdapter

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"
HAPROXY_HTTP_REQUIRER_SRC = "tests/integration/any_charm_http_requirer.py"
HAPROXY_INGRESS_REQUIRER_SRC = "tests/integration/any_charm_ingress_requirer.py"
HELPER_SRC = "tests/integration/helper.py"
INGRESS_LIB_SRC = "lib/charms/traefik_k8s/v2/ingress.py"
APT_LIB_SRC = "lib/charms/operator_libs_linux/v0/apt.py"
JUJU_WAIT_TIMEOUT = 10 * 60  # 10 minutes
HAPROXY_APP_NAME = "haproxy"
HAPROXY_CHANNEL = "2.8/edge"
HAPROXY_REVISION = 244
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
    model = request.config.getoption("--model")
    if model:
        juju = jubilant.Juju(model=model)
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju
        return

    keep_models = cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju


@pytest.fixture(scope="module", name="application")
def application_fixture(pytestconfig: pytest.Config, juju_machine: jubilant.Juju, charm: str):
    """Deploy the ingress-configurator application.

    Args:
        juju_machine: Jubilant juju_machine fixture.
        charm_file: Path to the packed charm file.

    Yields:
        The ingress-configurator app name.
    """
    metadata = yaml.safe_load(pathlib.Path("./charmcraft.yaml").read_text(encoding="UTF-8"))
    app_name = metadata["name"]
    if pytestconfig.getoption("--no-setup") and app_name in juju_machine.status().apps:
        yield app_name
        return
    juju_machine.deploy(
        charm=charm,
        app=app_name,
        base="ubuntu@24.04",
    )
    yield app_name


@pytest.fixture(scope="module", name="haproxy")
def haproxy_fixture(pytestconfig: pytest.Config, juju_machine: jubilant.Juju):
    """_summary_

    Args:
        juju_machine: Jubilant juju_machine fixture.

    Yields:
        The haproxy app name.
    """
    if pytestconfig.getoption("--no-setup") and HAPROXY_APP_NAME in juju_machine.status().apps:
        yield HAPROXY_APP_NAME
        return
    juju_machine.deploy(
        charm="haproxy",
        app=HAPROXY_APP_NAME,
        channel=HAPROXY_CHANNEL,
        revision=HAPROXY_REVISION,
        config={"external-hostname": MOCK_HAPROXY_HOSTNAME},
        base=HAPROXY_BASE,
    )
    juju_machine.deploy(
        charm="self-signed-certificates",
        app=CERTIFICATES_APP_NAME,
        channel=CERTIFICATES_CHANNEL,
        revision=CERTIFICATES_REVISION,
    )
    juju_machine.integrate(
        f"{CERTIFICATES_APP_NAME}:certificates", f"{HAPROXY_APP_NAME}:certificates"
    )
    juju_machine.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, CERTIFICATES_APP_NAME),
    )
    yield HAPROXY_APP_NAME


@pytest.fixture(scope="module", name="any_charm_backend")
def any_charm_backend_fixture(pytestconfig: pytest.Config, juju_machine: jubilant.Juju):
    """Deploy any-charm and configure it to serve as a requirer for the http interface."""
    if pytestconfig.getoption("--no-setup") and ANY_CHARM_APP_NAME in juju_machine.status().apps:
        yield ANY_CHARM_APP_NAME
        return
    juju_machine.deploy(
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
    juju_machine.wait(
        lambda status: jubilant.all_active(status, ANY_CHARM_APP_NAME, CERTIFICATES_APP_NAME)
    )
    for unit in juju_machine.status().apps[ANY_CHARM_APP_NAME].units:
        juju_machine.run(unit, "rpc", {"method": "start_server"})
    juju_machine.wait(lambda status: jubilant.all_active(status, ANY_CHARM_APP_NAME))
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
                DNSResolverAdapter(hostname, str(address)),
            )
            session.mount(
                f"http://{hostname}",
                DNSResolverAdapter(hostname, str(address)),
            )
        return session

    return _make_session


@pytest.fixture(scope="module", name="ingress_requirer")
def ingress_requirer_fixture(
    pytestconfig: pytest.Config, juju_machine: jubilant.Juju, application: str
):
    """Deploy and configure any-charm to serve as an ingress requirer for the ingress interface."""
    if (
        pytestconfig.getoption("--no-setup")
        and INGRESS_REQUIRER_APP_NAME in juju_machine.status().apps
    ):
        yield INGRESS_REQUIRER_APP_NAME
        return
    juju_machine.deploy(
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
    juju_machine.wait(
        lambda status: jubilant.all_active(
            status, INGRESS_REQUIRER_APP_NAME, "self-signed-certificates"
        )
    )
    for unit in juju_machine.status().apps[INGRESS_REQUIRER_APP_NAME].units:
        juju_machine.run(unit, "rpc", {"method": "start_server"})
    juju_machine.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{application}:ingress")
    juju_machine.wait(lambda status: jubilant.all_active(status, INGRESS_REQUIRER_APP_NAME))
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


@pytest.fixture(scope="module", name="application_with_tcp_server")
def application_with_tcp_server_fixture(application: str, juju_machine: jubilant.Juju):
    """Deploy the ingress-configurator application.

    Args:
        application: The ingress-configurator application name.
        juju_machine: Jubilant juju_machine fixture.

    Yields:
        The ingress-configurator app name.
    """
    juju_machine.wait(
        lambda status: jubilant.all_active(status, application),
    )
    command = "sudo snap install ping-pong-tcp; sudo snap set ping-pong-tcp host=0.0.0.0"
    juju_machine.ssh(target=f"{application}/0", command=command)
    yield application


@pytest.fixture(scope="session", name="machine_controller_name")
def machine_controller_name_fixture() -> str:
    """Return the name of the machine controller.

    Args:
        pytestconfig: The pytest config object.

    Returns:
        The machine controller name.
    """
    return "localhost"


@pytest.fixture(scope="module", name="juju_machine")
def juju_machine_fixture(
    machine_controller_name: str, pytestconfig: pytest.Config
) -> Generator[jubilant.Juju, None, None]:
    """Create a temporary machine model for haproxy and related dependencies.

    Args:
        machine_controller_name: Name of the machine controller.
        pytestconfig: The pytest config object.

    Yields:
        A jubilant.Juju instance connected to the temporary machine model.
    """
    keep = cast(bool, pytestconfig.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep, controller=machine_controller_name) as juju:
        juju.wait_timeout = JUJU_WAIT_TIMEOUT
        yield juju


@pytest.fixture(scope="module", name="machine_haproxy")
def machine_haproxy_fixture(
    juju_machine: jubilant.Juju, machine_controller_name: str
) -> Generator[tuple[jubilant.Juju, str, str], None, None]:
    """Deploy haproxy on the machine model and expose its haproxy-route endpoint as an offer.

    Args:
        juju_machine: jubilant.Juju instance for the machine model.
        machine_controller_name: Name of the machine controller.

    Yields:
        A tuple of (juju_machine juju, haproxy app name, offer URL).
    """
    juju_machine.deploy(
        charm="haproxy",
        app=HAPROXY_APP_NAME,
        channel=HAPROXY_CHANNEL,
        revision=HAPROXY_REVISION,
        config={"external-hostname": MOCK_HAPROXY_HOSTNAME},
        base=HAPROXY_BASE,
    )
    juju_machine.deploy(
        charm="self-signed-certificates",
        app=CERTIFICATES_APP_NAME,
        channel=CERTIFICATES_CHANNEL,
        revision=CERTIFICATES_REVISION,
    )
    juju_machine.integrate(
        f"{CERTIFICATES_APP_NAME}:certificates", f"{HAPROXY_APP_NAME}:certificates"
    )
    juju_machine.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, CERTIFICATES_APP_NAME),
    )
    juju_machine.offer(HAPROXY_APP_NAME, endpoint="haproxy-route")
    offer_url = f"{machine_controller_name}:admin/{juju_machine.model}.{HAPROXY_APP_NAME}"
    yield juju_machine, HAPROXY_APP_NAME, offer_url


@pytest.fixture(scope="module", name="k8s_application")
def k8s_application_fixture(
    charm: str,
    juju: jubilant.Juju,
    machine_haproxy: tuple[jubilant.Juju, str, str],
) -> Generator[str, None, None]:
    """Deploy the ingress-configurator on the K8s model and integrate with haproxy cross-model.

    Args:
        charm: Path to the packed charm file.
        juju: jubilant.Juju instance for the K8s model.
        machine_haproxy: Tuple of (machine juju, haproxy app name, offer URL).

    Yields:
        The ingress-configurator application name.
    """
    metadata = yaml.safe_load(pathlib.Path("./charmcraft.yaml").read_text(encoding="UTF-8"))
    app_name = metadata["name"]
    _, _, offer_url = machine_haproxy

    juju.deploy(charm=charm, app=app_name, base="ubuntu@24.04")
    juju.cli("consume", offer_url, include_model=True)
    juju.integrate(f"{app_name}:haproxy-route", HAPROXY_APP_NAME)
    yield app_name


@pytest.fixture(scope="module", name="k8s_ingress_requirer")
def k8s_ingress_requirer_fixture(
    juju: jubilant.Juju, k8s_application: str
) -> Generator[str, None, None]:
    """Deploy any-charm as an ingress requirer on the K8s model.

    Args:
        juju: jubilant.Juju instance for the K8s model.
        k8s_application: The ingress-configurator application name.

    Yields:
        The ingress requirer application name.
    """
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
    juju.wait(lambda status: jubilant.all_agents_idle(status, INGRESS_REQUIRER_APP_NAME))
    for unit in juju.status().apps[INGRESS_REQUIRER_APP_NAME].units:
        juju.run(unit, "rpc", {"method": "start_server"})
    juju.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{k8s_application}:ingress")
    juju.wait(lambda status: jubilant.all_active(status, INGRESS_REQUIRER_APP_NAME))
    yield INGRESS_REQUIRER_APP_NAME
