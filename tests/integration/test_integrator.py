# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Test the charm in integrator mode."""
import ipaddress

import jubilant
from requests import Session

from .conftest import MOCK_HAPROXY_HOSTNAME


def test_integrator(
    juju: jubilant.Juju, application: str, haproxy: str, ingress_requirer: str, session: Session
):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
    """
    juju.integrate("haproxy:haproxy-route", f"{application}:haproxy-route")
    any_charm_address = ipaddress.ip_address(
        juju.status().apps[ingress_requirer].units[f"{ingress_requirer}/0"].public_address
    )
    juju.config(
        app=application, values={"backend_address": str(any_charm_address), "backend_port": 80}
    )
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )

    response = session.get(
        f"https://{MOCK_HAPROXY_HOSTNAME}",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert "Apache2 Default Page" in response.text


def test_config(
    juju: jubilant.Juju, application: str, haproxy: str, ingress_requirer: str, session: Session
):
    """Test the charm configuration in integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
    """
    juju.config(app=application, values={"paths": "/api/v1,/api/v2", "subdomains": "api"})
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )

    response = session.get(
        f"https://api.{MOCK_HAPROXY_HOSTNAME}/api/v1",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert response.status_code == 200
    assert "v1 ok!" in response.text
    response = session.get(
        f"https://api.{MOCK_HAPROXY_HOSTNAME}/api/v2",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert response.status_code == 200
    assert "v2 ok!" in response.text
