# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests configuration."""

import json
import pathlib
import typing

import jubilant
import pytest
import yaml

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"
HAPROXY_HTTP_REQUIRER_SRC = "tests/integration/any_charm_http_requirer.py"
HAPROXY_INGRESS_REQUIRER_SRC = "tests/integration/any_charm_ingress_requirer.py"
HELPER_SRC = "tests/integration/helper.py"
INGRESS_LIB_SRC = "lib/charms/traefik_k8s/v2/ingress.py"
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

    keep_models = typing.cast(bool, request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = 10 * 60
        yield juju
        show_debug_log(juju)
        return


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
        revision=194,
        config={"external-hostname": MOCK_HAPROXY_HOSTNAME},
        base="ubuntu@24.04",
    )
    juju.deploy(charm="self-signed-certificates", channel="1/stable", revision=263)
    juju.integrate("self-signed-certificates:certificates", f"{haproxy_app_name}:certificates")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy_app_name, "self-signed-certificates")
    )
    yield haproxy_app_name


@pytest.fixture(scope="module", name="any_charm_backend")
def any_charm_backend_fixture(juju: jubilant.Juju):
    """Deploy any-charm and configure it to spin up an apache web server."""
    app_name = "backend-requirer"
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=app_name,
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
    juju.wait(lambda status: jubilant.all_active(status, app_name, "self-signed-certificates"))
    for unit in juju.status().apps[app_name].units.keys():
        juju.run(unit, "rpc", {"method": "start_server"})
    juju.wait(lambda status: jubilant.all_active(status, app_name))
    yield app_name


@pytest.fixture(scope="module", name="ingress_requirer")
def ingress_requirer_fixture(juju: jubilant.Juju):
    """Deploy and configure any-charm to serve as an ingress requirer for the ingress interface."""
    app_name = "ingress-requirer"
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=app_name,
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
    juju.wait(lambda status: jubilant.all_active(status, app_name, "self-signed-certificates"))
    juju.run(f"{app_name}/0", "rpc", {"method": "start_server"})
    yield app_name
