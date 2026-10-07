# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

from typing import Callable

import jubilant
import pytest
from requests import Session

from ..conftest import MOCK_HAPROXY_HOSTNAME, SELF_SIGNED_CERTIFICATES_APP_NAME, get_unit_addresses


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
            status, haproxy, application, any_charm_backend, SELF_SIGNED_CERTIFICATES_APP_NAME
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
                status, haproxy, application, any_charm_backend, SELF_SIGNED_CERTIFICATES_APP_NAME
            )
            and jubilant.all_agents_idle(
                status, haproxy, application, any_charm_backend, SELF_SIGNED_CERTIFICATES_APP_NAME
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
        response = session.get(
            f"https://{MOCK_HAPROXY_HOSTNAME}/api/{path_component}/", timeout=30, verify=False
        )
        assert response.status_code == 200 and f"{path_component} ok!" in response.text

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
        response = session.get(
            f"https://{subdomain}.{MOCK_HAPROXY_HOSTNAME}/api/v1/", timeout=30, verify=False
        )
        assert response.status_code == 200 and "v1 ok!" in response.text
