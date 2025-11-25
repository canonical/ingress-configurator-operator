# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

from typing import Callable

import jubilant
from requests import Session

from .conftest import MOCK_HAPROXY_HOSTNAME, get_unit_addresses


def test_adapter_end_to_end_routing(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    ingress_requirer: str,
    http_session: Callable[..., Session],
):
    """Test for integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
        http_session: Modified requests session fixture for making HTTP requests.
    """
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )

    session = http_session(
        dns_entries=[(MOCK_HAPROXY_HOSTNAME, str(get_unit_addresses(juju, haproxy)[0]))]
    )
    response = session.get(f"https://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert "Apache2 Default Page" in response.text


def test_adapter_http(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    ingress_requirer: str,
    http_session: Callable[..., Session],
):
    """Test for allow-http config.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
        http_session: Modified requests session fixture for making HTTP requests.
    """
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    addr = str(get_unit_addresses(juju, haproxy)[0])
    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, addr)])
    response = session.get(f"https://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert "Apache2 Default Page" in response.text

    response = session.get(f"http://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert response.history[0].status_code == 302
    juju.config(application, {"allow-http": True})
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application),
        error=jubilant.any_error,
    )

    response = session.get(f"http://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert "Apache2 Default Page" in response.text
