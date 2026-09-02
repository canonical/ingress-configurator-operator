# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests configuration."""

import json
import pathlib
import subprocess  # nosec: B404
import tempfile
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Callable, Generator

import jubilant
import pytest
import yaml
from requests import Session

from .helper import DNSResolverAdapter

MOCK_HAPROXY_HOSTNAME = "haproxy.internal"
INGRESS_REQUIRER_SRC = pathlib.Path("tests/integration/any_charm_apache.py")
INGRESS_REQUIRER_HTTPS_SRC = pathlib.Path("tests/integration/any_charm_https.py")
HELPER_SRC = pathlib.Path("tests/integration/helper.py")
INGRESS_LIB_SRC = pathlib.Path("lib/charms/traefik_k8s/v2/ingress.py")
JUJU_WAIT_TIMEOUT = 10 * 60
HAPROXY_APP_NAME = "haproxy"
HAPROXY_CHANNEL = "2.8/edge"
HAPROXY_REVISION = 473
HAPROXY_BASE = "ubuntu@24.04"
CERTIFICATES_APP_NAME = "self-signed-certificates"
CERTIFICATES_CHANNEL = "1/stable"
CERTIFICATES_REVISION = 588
ANY_CHARM_APP_NAME = "any-charm-backend"
HTTPS_BACKEND_APP_NAME = "any-charm-https-backend"
CONTENT_CACHE_APP_NAME = "content-cache"
CONTENT_CACHE_CHANNEL = "1/edge"
CONTENT_CACHE_REVISION = 530
INGRESS_REQUIRER_APP_NAME = "ingress-requirer"
APP_NAME = "ingress-configurator"

# Gateway-route (Kubernetes Gateway API) test configuration.
GATEWAY_API_INTEGRATOR_APP_NAME = "gateway-api-integrator"
GATEWAY_API_INTEGRATOR_CHANNEL = "1/edge"
GATEWAY_API_INTEGRATOR_REVISION = 172
# GatewayClass provided by the Canonical Kubernetes used in CI.
GATEWAY_CLASS = "ck-gateway"
EXTERNAL_HOSTNAME = "gateway.internal"
GATEWAY_CERTIFICATES_CHANNEL = "1/edge"
# max-age (seconds) for the Strict-Transport-Security header the provider publishes when
# HTTPS is enforced; a non-default value so the enforced-HTTPS test verifies it flows through.
GATEWAY_HSTS_MAX_AGE = 15552000

# Closed-ports backend (flask-k8s, is_port_open=False).
# Also reused by the enforced-HTTPS test, which runs in a separate model.
GATEWAY_CONFIGURATOR_CLOSED_PORTS = "configurator-closed"
GATEWAY_BACKEND_CLOSED_PORTS = "backend-closed"
HOSTNAME_BACKEND_CLOSED_PORTS = "closed.gateway.internal"
ADDITIONAL_HOSTNAME_BACKEND_CLOSED_PORTS = "alt-closed.gateway.internal"

# Open-ports backend (any-charm-k8s, is_port_open=True).
GATEWAY_CONFIGURATOR_OPEN_PORTS = "configurator-open"
GATEWAY_BACKEND_OPEN_PORTS = "backend-open"
HOSTNAME_BACKEND_OPEN_PORTS = "open.gateway.internal"
ADDITIONAL_HOSTNAME_BACKEND_OPEN_PORTS = "alt-open.gateway.internal"
INGRESS_BACKEND_PORT = 8000
GATEWAY_BACKEND_OPEN_PATH = "/api/v1"
GATEWAY_BACKEND_OPEN_BODY = "ok from open-ports backend"


@pytest.fixture(scope="session", name="charm")
def charm_fixture(charm_paths) -> str:
    """Get the built ingress-configurator charm path."""
    return charm_paths["ingress-configurator"].path


@pytest.fixture(scope="session", name="lxd_controller")
def lxd_controller_fixture() -> str:
    """Return the name of the machine controller.

    Returns:
        The machine controller name.
    """
    return "concierge-lxd"


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
    return "concierge-k8s"


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
        juju.cli("show-cloud", "--controller", k8s_controller, "k8s", include_model=False)
    except jubilant.CLIError:
        # Cloud not yet registered on this controller; add it now.
        juju.cli("add-cloud", "--controller", k8s_controller, "k8s", include_model=False)
    try:
        juju.show_model(f"{k8s_controller}:{k8s_model}")
    except jubilant.CLIError:
        # Model not yet created on this controller; create it now.
        # Use cli() directly to avoid add_model() mutating juju.model on this instance.
        juju.cli(
            "add-model",
            "--no-switch",
            "--controller",
            k8s_controller,
            k8s_model,
            "k8s",
            include_model=False,
        )
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
    if app_name in juju.status().apps:
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
    if HAPROXY_APP_NAME in juju.status().apps:
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
    # Allow haproxy to verify content-cache's TLS certificate when protocol=https is used
    # in the haproxy-route relation (full HTTPS chain: haproxy → content-cache → backend).
    juju.integrate(f"{CERTIFICATES_APP_NAME}:send-ca-cert", f"{HAPROXY_APP_NAME}:receive-ca-certs")
    juju.offer(HAPROXY_APP_NAME, endpoint="haproxy-route")
    yield HAPROXY_APP_NAME


@pytest.fixture(scope="module", name="any_charm_backend")
def any_charm_backend_fixture(
    pytestconfig: pytest.Config, juju: jubilant.Juju, lxd_controller: str, lxd_model: str
):
    """Deploy any-charm and configure it to serve as a requirer for the http interface."""
    if ANY_CHARM_APP_NAME in juju.status().apps:
        yield ANY_CHARM_APP_NAME
        return
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=ANY_CHARM_APP_NAME,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": INGRESS_REQUIRER_SRC.read_text(encoding="utf-8"),
                    "ingress.py": INGRESS_LIB_SRC.read_text(encoding="utf-8"),
                    "config.json": json.dumps(
                        {
                            "port": 80,
                            "pages": {
                                "/api/v1/index.html": "v1 ok!",
                                "/api/v2/index.html": "v2 ok!",
                            },
                        }
                    ),
                }
            ),
            "python-packages": "\n".join(["pydantic", "charmlibs-apt"]),
        },
        num_units=2,
    )
    yield ANY_CHARM_APP_NAME


def _generate_backend_tls(hostname: str) -> tuple[str, str, str]:
    """Generate a throwaway CA and a server certificate valid for ``hostname``.

    The server certificate carries a ``DNS:<hostname>`` SAN (and no IP SAN), so it is
    independent of any particular unit's address and can be served identically by every
    backend unit.  content-cache verifies the backend TLS connection against this hostname
    via ``proxy_ssl_name``, and trusts the returned CA through ``receive-ca-cert``.

    The material is generated at runtime (never committed), so no secret is stored in the repo.

    Args:
        hostname: The hostname to embed as the certificate CN and SAN.

    Returns:
        A tuple of ``(ca_cert_pem, server_cert_pem, server_key_pem)``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        ca_key, ca_crt = tmp_path / "ca.key", tmp_path / "ca.crt"
        srv_key, srv_csr, srv_crt = (
            tmp_path / "srv.key",
            tmp_path / "srv.csr",
            tmp_path / "srv.crt",
        )
        san_ext = tmp_path / "san.ext"
        san_ext.write_text(f"subjectAltName=DNS:{hostname}\n", encoding="utf-8")

        def _run(args: list[str]) -> None:
            subprocess.run(args, check=True, capture_output=True)  # nosec: B603

        _run(["openssl", "genrsa", "-out", str(ca_key), "2048"])
        _run(
            [
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(ca_key),
                "-sha256",
                "-days",
                "3650",
                "-out",
                str(ca_crt),
                "-subj",
                "/CN=Test Backend CA",
            ]
        )
        _run(["openssl", "genrsa", "-out", str(srv_key), "2048"])
        _run(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(srv_key),
                "-out",
                str(srv_csr),
                "-subj",
                f"/CN={hostname}",
            ]
        )
        _run(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(srv_csr),
                "-CA",
                str(ca_crt),
                "-CAkey",
                str(ca_key),
                "-CAcreateserial",
                "-out",
                str(srv_crt),
                "-days",
                "3650",
                "-sha256",
                "-extfile",
                str(san_ext),
            ]
        )
        return (
            ca_crt.read_text(encoding="utf-8"),
            srv_crt.read_text(encoding="utf-8"),
            srv_key.read_text(encoding="utf-8"),
        )


@pytest.fixture(scope="module", name="any_charm_backend_https")
def any_charm_backend_https_fixture(
    pytestconfig: pytest.Config, juju: jubilant.Juju, lxd_controller: str, lxd_model: str
):
    """Deploy a 2-unit any-charm serving HTTPS on port 443 with a shared CA-signed cert.

    Every unit serves the identical, hostname-scoped certificate (no IP SAN) and publishes
    the same CA, so content-cache trusts all backend units and can load-balance across them.
    """
    if HTTPS_BACKEND_APP_NAME in juju.status().apps:
        yield HTTPS_BACKEND_APP_NAME
        return
    ca_cert, server_cert, server_key = _generate_backend_tls(MOCK_HAPROXY_HOSTNAME)
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=HTTPS_BACKEND_APP_NAME,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": INGRESS_REQUIRER_HTTPS_SRC.read_text(encoding="utf-8"),
                    "ingress.py": INGRESS_LIB_SRC.read_text(encoding="utf-8"),
                    "config.json": json.dumps(
                        {
                            "port": 443,
                            "pages": {
                                "/api/v1/index.html": "v1 ok!",
                                "/api/v2/index.html": "v2 ok!",
                            },
                            "backend_hostname": MOCK_HAPROXY_HOSTNAME,
                            "ca_cert": ca_cert,
                            "server_cert": server_cert,
                            "server_key": server_key,
                        }
                    ),
                }
            ),
            "python-packages": "pydantic",
        },
        num_units=2,
    )
    yield HTTPS_BACKEND_APP_NAME


@pytest.fixture(scope="module", name="content_cache")
def content_cache_fixture(juju: jubilant.Juju):
    """Deploy content-cache from the 1/edge channel.

    Args:
        juju: Jubilant juju fixture.

    Yields:
        The content-cache application name.
    """
    if CONTENT_CACHE_APP_NAME in juju.status().apps:
        yield CONTENT_CACHE_APP_NAME
        return
    juju.deploy(
        charm="content-cache",
        app=CONTENT_CACHE_APP_NAME,
        channel=CONTENT_CACHE_CHANNEL,
        revision=CONTENT_CACHE_REVISION,
        base="ubuntu@24.04",
    )
    yield CONTENT_CACHE_APP_NAME


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
    if INGRESS_REQUIRER_APP_NAME in juju.status().apps:
        yield INGRESS_REQUIRER_APP_NAME
        return
    juju.deploy(
        charm="any-charm",
        channel="beta",
        app=INGRESS_REQUIRER_APP_NAME,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": INGRESS_REQUIRER_SRC.read_text(encoding="utf-8"),
                    "ingress.py": INGRESS_LIB_SRC.read_text(encoding="utf-8"),
                }
            ),
            "python-packages": "\n".join(["pydantic", "charmlibs-apt"]),
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
        lambda status: jubilant.all_agents_idle(status, application),
        error=jubilant.any_error,
    )
    juju.exec("sudo snap install ping-pong-tcp", unit=f"{application}/leader")
    juju.exec("sudo snap set ping-pong-tcp host=0.0.0.0", unit=f"{application}/leader")
    yield application


@pytest.fixture(scope="module", name="k8s_ingress_requirer")
def k8s_ingress_requirer_fixture(
    pytestconfig: pytest.Config,
    charm: str,
    juju_k8s: jubilant.Juju,
    lxd_controller: str,
    lxd_model: str,
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
    if APP_NAME in juju_k8s.status().apps:
        yield APP_NAME
        return
    juju_k8s.deploy(charm=charm, app=APP_NAME, trust=True)
    juju_k8s.deploy(
        charm="flask-k8s",
        channel="latest/edge",
        app=INGRESS_REQUIRER_APP_NAME,
    )
    juju_k8s.integrate(
        f"{APP_NAME}:haproxy-route", f"{lxd_controller}:admin/{lxd_model}.{HAPROXY_APP_NAME}"
    )
    juju_k8s.integrate(f"{INGRESS_REQUIRER_APP_NAME}:ingress", f"{APP_NAME}:ingress")
    juju_k8s.wait(
        lambda status: jubilant.all_agents_idle(status, APP_NAME, INGRESS_REQUIRER_APP_NAME),
        error=jubilant.any_error,
    )
    yield INGRESS_REQUIRER_APP_NAME


@pytest.fixture(scope="module", name="gateway_api_integrator")
def gateway_api_integrator_fixture(juju_k8s: jubilant.Juju) -> str:
    """Deploy gateway-api-integrator as the shared gateway-route provider (HTTP by default).

    The provider is deployed with ``enforce-https=False`` (HTTP only). Tests needing HTTPS
    reconfigure it (``enforce-https=True`` plus a ``certificates`` relation). This fixture does
    not wait for the application to settle.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.

    Returns:
        The gateway-api-integrator application name.
    """
    juju_k8s.deploy(
        charm=GATEWAY_API_INTEGRATOR_APP_NAME,
        channel=GATEWAY_API_INTEGRATOR_CHANNEL,
        revision=GATEWAY_API_INTEGRATOR_REVISION,
        base="ubuntu@24.04",
        trust=True,
        config={"gateway-class": GATEWAY_CLASS, "enforce-https": False},
    )
    return GATEWAY_API_INTEGRATOR_APP_NAME


def deploy_ingress_configurator_for_gateway_route(
    juju: jubilant.Juju, charm: str, app: str, gateway: str, config: dict | None = None
) -> str:
    """Deploy an ingress-configurator instance (gateway-route requirer); does not wait.

    Args:
        juju: Jubilant Juju instance for the Kubernetes model.
        charm: Path to the packed ingress-configurator charm.
        app: Application name to deploy under.
        gateway: gateway-route provider app name to integrate with.
        config: Optional charm config to apply at deploy time.

    Returns:
        The deployed application name.
    """
    juju.deploy(charm=charm, app=app, trust=True, config=config or {})
    juju.integrate(f"{app}:gateway-route", f"{gateway}:gateway-route")
    return app


@pytest.fixture(scope="module", name="backend_closed")
def backend_closed_fixture(juju_k8s: jubilant.Juju) -> str:
    """Deploy a flask-k8s workload that keeps its port closed (``is_port_open=False``).

    flask-k8s does not open its workload port, so a consumer relating over ``ingress`` sees
    ``is_port_open=False``, driving the closed-ports branch of the adapter decision tree. This
    fixture does not wait for the application to settle.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.

    Returns:
        The deployed application name.
    """
    juju_k8s.deploy(charm="flask-k8s", app=GATEWAY_BACKEND_CLOSED_PORTS, channel="latest/edge")
    return GATEWAY_BACKEND_CLOSED_PORTS


@pytest.fixture(scope="module", name="backend_open")
def backend_open_fixture(juju_k8s: jubilant.Juju) -> str:
    """Deploy an any-charm-k8s workload that opens its port (``is_port_open=True``).

    The backend declares ingress on a fixed port, opens that port (so the ingress databag
    reports ``is_port_open=True``) and serves a catch-all HTTP response from its workload
    container, driving the open-ports branch of the adapter decision tree. This fixture does not
    wait for the application to settle.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.

    Returns:
        The deployed application name.
    """
    juju_k8s.deploy(
        charm="any-charm-k8s",
        channel="beta",
        app=GATEWAY_BACKEND_OPEN_PORTS,
        config={
            "src-overwrite": json.dumps(
                {
                    "any_charm.py": INGRESS_REQUIRER_SRC.read_text(encoding="utf-8"),
                    "ingress.py": INGRESS_LIB_SRC.read_text(encoding="utf-8"),
                    "config.json": json.dumps(
                        {
                            "port": INGRESS_BACKEND_PORT,
                            "pages": {GATEWAY_BACKEND_OPEN_PATH: GATEWAY_BACKEND_OPEN_BODY},
                        }
                    ),
                }
            ),
            "python-packages": "\n".join(["pydantic", "charmlibs-apt"]),
        },
    )
    return GATEWAY_BACKEND_OPEN_PORTS
