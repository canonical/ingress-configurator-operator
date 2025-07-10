# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

import jubilant

from .helper import haproxy_request


def test_adapter(juju: jubilant.Juju, application: str, haproxy: str, ingress_requirer: str):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
    """
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju.integrate(f"{ingress_requirer}:ingress", f"{application}:ingress")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )

    haproxy_address = juju.status().apps[haproxy].units[f"{haproxy}/0"].public_address
    response = haproxy_request(haproxy_address)
    assert "Apache2 Default Page" in response.text
