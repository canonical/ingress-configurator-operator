# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

import ipaddress

import jubilant

from .helper import haproxy_request


def test_integrator(juju: jubilant.Juju, application: str, haproxy: str, http_requirer: str):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        http_requirer: Any charm running an apache webserver.
    """
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
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

    haproxy_address = juju.status().apps[haproxy].units[f"{haproxy}/0"].public_address
    response = haproxy_request(haproxy_address)
    assert "Apache2 Default Page" in response.text
