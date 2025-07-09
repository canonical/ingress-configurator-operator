# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

import jubilant

from .helper import haproxy_request


def test_integrator(juju: jubilant.Juju, application: str, haproxy: str, any_charm_backend: str):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        any_charm_backend: Any charm running an apache webserver.
    """
    juju.integrate("haproxy:haproxy-route", f"{application}:haproxy-route")
    backend_addresses = ",".join(
        [unit.public_address for unit in juju.status().apps[any_charm_backend].units.values()]
    )
    juju.config(
        app=application, values={"backend-addresses": backend_addresses, "backend-ports": 80}
    )
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, any_charm_backend),
        error=jubilant.any_error,
    )

    haproxy_address = juju.status().apps[haproxy].units[f"{haproxy}/0"].public_address
    response = haproxy_request(haproxy_address)
    assert "Apache2 Default Page" in response.text
