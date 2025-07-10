# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Test the charm in integrator mode."""
import ipaddress
from typing import Callable

import jubilant
from requests import Session

from .conftest import MOCK_HAPROXY_HOSTNAME


def test_ingress_integrator_end_to_end_routing(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    any_charm_backend: str,
    make_session: Callable[..., Session],
):
    """Test the integrator reaches the backend successfully through integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
        make_session: Modified requests session fixture for making HTTP requests.
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
    session = make_session()
    response = session.get(
        f"https://{MOCK_HAPROXY_HOSTNAME}",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert "Apache2 Default Page" in response.text


def test_config_subdomains_and_paths(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    ingress_requirer: str,
    make_session: Callable[..., Session],
):
    """Test the charm configuration in integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
        make_session: Modified requests session fixture for making HTTP requests.
    """
    juju.config(app=application, values={"paths": "/api/v1,/api/v2", "subdomains": "api"})
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    session = make_session(f"api.{MOCK_HAPROXY_HOSTNAME}")
    response = session.get(
        f"https://api.{MOCK_HAPROXY_HOSTNAME}/api/v1/",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert response.status_code == 200
    assert "v1 ok!" in response.text
    response = session.get(
        f"https://api.{MOCK_HAPROXY_HOSTNAME}/api/v2/",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert response.status_code == 200
    assert "v2 ok!" in response.text
    response = session.get(
        f"https://{MOCK_HAPROXY_HOSTNAME}",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    assert "Default page for the haproxy-operator charm" in response.text
