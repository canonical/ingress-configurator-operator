# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests configuration."""

import json
import pathlib
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Callable, Generator

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
JUJU_WAIT_TIMEOUT = 10 * 60
HAPROXY_APP_NAME = "haproxy"
HAPROXY_CHANNEL = "2.8/edge"
HAPROXY_REVISION = 387
HAPROXY_BASE = "ubuntu@24.04"
CERTIFICATES_APP_NAME = "self-signed-certificates"
CERTIFICATES_CHANNEL = "1/stable"
CERTIFICATES_REVISION = 588
ANY_CHARM_APP_NAME = "any-charm-backend"
INGRESS_REQUIRER_APP_NAME = "ingress-requirer"


@pytest.fixture(scope="session", name="charm")
def charm_fixture(pytestconfig: pytest.Config):
    """Pytest fixture that packs the charm and returns the filename, or --charm-file if set."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "--charm-file must be set"
    yield charm


@pytest.fixture(scope="session", name="lxd_controller")
def lxd_controller_fixture() -> str:
    """Return the name of the machine controller.

    Returns:
        The machine controller name.
    """
    return "localhost"


@pytest.fixture(scope="session", name="lxd_model")
def lxd_model_fixture() -> str:
    """Return the name of the machine model.

    Returns:
        The machine model name.
    """
    return "testing"


@pytest.fixture(scope="session", name="k8s_controller")
def k8s_controller_fixture() -> str:
    """Return the name of the Kubernetes controller.

    Returns:
        The Kubernetes controller name.
    """
    return "localhost"


@pytest.fixture(scope="session", name="k8s_model")
def k8s_model_fixture() -> str:
    """Return the name of the machine model.

    Returns:
        The machine model name.
    """
    return "k8s"


@pytest.fixture(scope="module", name="juju")
def juju_fixture(lxd_controller: str, lxd_model: str):
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""
    juju = jubilant.Juju(model=f"{lxd_controller}:{lxd_model}")
    juju.wait_timeout = JUJU_WAIT_TIMEOUT
    yield juju


@pytest.fixture(scope="module", name="juju_k8s")
def juju_k8s_fixture(juju: jubilant.Juju, k8s_controller: str, k8s_model: str):
    """Pytest fixture that wraps :meth:`jubilant.with_model`."""
    try:
        juju.cli(
            "add-cloud",
            "--controller",
            k8s_controller,
            "k8s",
            include_model=False,
        )
    except jubilant.CLIError as exc:
        # Ignore the error only if the cloud already exists; re-raise for all other failures.
        if "already exists" not in str(exc):
            raise
    try:
        juju.cli("add-model", "--no-switch", k8s_model, "k8s", include_model=False)
    except jubilant.CLIError as exc:
        # Ignore the error only if the model already exists; re-raise for all other failures.
        if "already exists" not in str(exc):
            raise
    new_juju = jubilant.Juju(model=f"{k8s_controller}:{k8s_model}")
    new_juju.wait_timeout = JUJU_WAIT_TIMEOUT
    yield new_juju


@pytest.fixture(scope="module", name="application")
def application_fixture(
    pytestconfig: pytest.Config,
    juju: jubilant.Juju,
    charm: str,
):
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
    juju.offer(HAPROXY_APP_NAME, endpoint="haproxy-route")
    yield HAPROXY_APP_NAME


@pytest.fixture(scope="module", name="any_charm_backend")
def any_charm_backend_fixture(
    pytestconfig: pytest.Config, juju: jubilant.Juju, lxd_controller: str, lxd_model: str
):
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
    juju.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{application}:ingress")
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
def application_with_tcp_server_fixture(application: str, juju: jubilant.Juju):
    """Deploy the ingress-configurator application.

    Args:
        application: The ingress-configurator application name.
        juju: Jubilant juju fixture.

    Yields:
        The ingress-configurator app name.
    """
    juju.wait(
        lambda status: jubilant.all_active(status, application),
    )
    command = "sudo snap install ping-pong-tcp; sudo snap set ping-pong-tcp host=0.0.0.0"
    juju.ssh(target=f"{application}/0", command=command)
    yield application


@pytest.fixture(scope="module", name="k8s_ingress_requirer")
def k8s_ingress_requirer_fixture(
    charm: str, juju_k8s: jubilant.Juju, lxd_controller: str, lxd_model: str
) -> Generator[str, None, None]:
    """Deploy any-charm as an ingress requirer on the K8s model.

    Args:
        charm: Path to the packed charm file.
        juju_k8s: jubilant.Juju instance for the K8s model.
        lxd_controller: the LXD controller name.
        lxd_model: the LXD model name.

    Yields:
        The ingress requirer application name.
    """
    metadata = yaml.safe_load(pathlib.Path("./charmcraft.yaml").read_text(encoding="UTF-8"))
    app_name = metadata["name"]

    juju_k8s.deploy(charm=charm, app=app_name, trust=True)
    juju_k8s.deploy(
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
    juju_k8s.integrate(
        f"{app_name}:haproxy-route", f"{lxd_controller}:admin/{lxd_model}.{HAPROXY_APP_NAME}"
    )
    juju_k8s.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{app_name}:ingress")
    juju_k8s.wait(
        lambda status: jubilant.all_agents_idle(status, app_name, INGRESS_REQUIRER_APP_NAME)
    )
    yield INGRESS_REQUIRER_APP_NAME
