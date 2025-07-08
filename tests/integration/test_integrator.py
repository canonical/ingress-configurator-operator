# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Test the charm in integrator mode."""

import ipaddress

import jubilant
from requests import Session

from .conftest import MOCK_HAPROXY_HOSTNAME
from .helper import DNSResolverHTTPSAdapter


def test_integrator(juju: jubilant.Juju, application: str, haproxy: str, http_requirer: str):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        http_requirer: Any charm running an apache webserver.
    """
    juju.integrate("haproxy:haproxy-route", f"{application}:haproxy-route")
    any_charm_address = ipaddress.ip_address(
        juju.status().apps[http_requirer].units[f"{http_requirer}/0"].public_address
    )
    juju.config(
        app=application, values={"backend_address": str(any_charm_address), "backend_port": 80}
    )
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, http_requirer),
        error=jubilant.any_error,
    )

    haproxy_address = ipaddress.ip_address(
        juju.status().apps[haproxy].units[f"{haproxy}/0"].public_address
    )

    session = Session()
    session.mount(
        "https://",
        DNSResolverHTTPSAdapter(MOCK_HAPROXY_HOSTNAME, str(haproxy_address)),
    )
    response = session.get(
        f"https://{MOCK_HAPROXY_HOSTNAME}",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert "Apache2 Default Page" in response.text
