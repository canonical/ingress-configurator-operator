# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

from typing import Callable

import jubilant
import pytest
from requests import Session
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

from ..conftest import CERTIFICATES_APP_NAME, MOCK_HAPROXY_HOSTNAME, get_unit_addresses


@retry(
    stop=stop_after_delay(60),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
)
def _assert_routed_response(session: Session, url: str, expected_body: str) -> None:
    """Request a URL until haproxy routes it to the expected backend response.

    Haproxy may take a short moment to reload after a relation/config change is
    applied, even once Juju reports the units as active and idle, so retry until
    the new routing rules are in effect.

    Args:
        session: Requests session used to make the HTTP call.
        url: URL to request.
        expected_body: Substring expected in the response body once routed correctly.
    """
    response = session.get(url, timeout=30, verify=False)
    assert response.status_code == 200 and expected_body in response.text, (
        f"Unexpected response for {url}: status={response.status_code}, body={response.text!r}"
    )


@pytest.mark.abort_on_fail
def test_config_hostnames_and_paths(
    juju_lxd: jubilant.Juju,
    application: str,
    haproxy: str,
    any_charm_backend: str,
    http_session: Callable[..., Session],
):
    """Test the charm configuration in integrator mode.

    Args:
        juju_lxd: Jubilant Juju instance for the LXD model.
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        any_charm_backend: Any charm running an apache webserver.
        http_session: Modified requests session fixture for making HTTP requests.
    """
    juju_lxd.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju_lxd.wait(
        lambda status: jubilant.all_agents_idle(
            status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
        ),
        error=jubilant.any_error,
    )
    backend_addresses = ",".join(
        [str(address) for address in get_unit_addresses(juju_lxd, any_charm_backend)]
    )
    juju_lxd.config(
        app=application,
        values={
            "backend-addresses": backend_addresses,
            "backend-ports": 80,
            "paths": "/api/v1,/api/v2",
        },
    )
    juju_lxd.wait(
        lambda status: (
            jubilant.all_active(
                status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
            )
            and jubilant.all_agents_idle(
                status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
            )
        ),
        error=jubilant.any_error,
    )

    haproxy_address = str(get_unit_addresses(juju_lxd, haproxy)[0])
    session = http_session(
        dns_entries=[
            (MOCK_HAPROXY_HOSTNAME, haproxy_address),
            (f"api.{MOCK_HAPROXY_HOSTNAME}", haproxy_address),
            (f"api2.{MOCK_HAPROXY_HOSTNAME}", haproxy_address),
            (f"api3.{MOCK_HAPROXY_HOSTNAME}", haproxy_address),
        ]
    )

    for path_component in ["v1", "v2"]:
        _assert_routed_response(
            session,
            f"https://{MOCK_HAPROXY_HOSTNAME}/api/{path_component}/",
            f"{path_component} ok!",
        )

    juju_lxd.config(
        app=application,
        values={
            "paths": "/api/v1",
            "hostname": f"api.{MOCK_HAPROXY_HOSTNAME}",
            "additional-hostnames": f"api2.{MOCK_HAPROXY_HOSTNAME},api3.{MOCK_HAPROXY_HOSTNAME}",
        },
    )
    juju_lxd.wait(
        lambda status: (
            jubilant.all_active(status, haproxy, application, any_charm_backend)
            and jubilant.all_agents_idle(status, haproxy, application, any_charm_backend)
        ),
        error=jubilant.any_error,
    )

    for subdomain in ["api", "api2", "api3"]:
        _assert_routed_response(
            session,
            f"https://{subdomain}.{MOCK_HAPROXY_HOSTNAME}/api/v1/",
            "v1 ok!",
        )
