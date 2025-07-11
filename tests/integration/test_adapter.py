# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

from typing import Callable

import jubilant
from requests import Session

from .conftest import MOCK_HAPROXY_HOSTNAME
from .helper import haproxy_request


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
    juju.integrate(f"{ingress_requirer}:ingress", f"{application}:ingress")
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )

    session = http_session()
    response = haproxy_request(session, f"https://{MOCK_HAPROXY_HOSTNAME}")
    assert "Apache2 Default Page" in response.text
