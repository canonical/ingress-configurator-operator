# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in adapter mode."""

from typing import Callable

import jubilant
import pytest
from requests import Session

from .conftest import (
    APP_NAME,
    HAPROXY_APP_NAME,
    INGRESS_REQUIRER_APP_NAME,
    MOCK_HAPROXY_HOSTNAME,
    deploy_ingress_requirer,
    deploy_with_haproxy,
    get_unit_addresses,
)


@pytest.mark.juju_setup
def test_deploy_with_haproxy(juju: jubilant.Juju, charm: str):
    deploy_with_haproxy(juju, charm)


@pytest.mark.juju_setup
def test_deploy_ingress_requirer(juju: jubilant.Juju):
    deploy_ingress_requirer(juju)


def test_adapter_end_to_end_routing(juju: jubilant.Juju, http_session: Callable[..., Session]):
    """Test for integrator mode."""
    juju.integrate(f"{HAPROXY_APP_NAME}:haproxy-route", f"{APP_NAME}:haproxy-route")
    apps = (HAPROXY_APP_NAME, APP_NAME, INGRESS_REQUIRER_APP_NAME)
    juju.wait(lambda status: jubilant.all_active(status, *apps), error=jubilant.any_error)

    session = http_session(
        dns_entries=[(MOCK_HAPROXY_HOSTNAME, str(get_unit_addresses(juju, HAPROXY_APP_NAME)[0]))]
    )
    response = session.get(f"https://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert "Apache2 Default Page" in response.text


def test_adapter_http(juju: jubilant.Juju, http_session: Callable[..., Session]):
    """Test for allow-http config."""
    juju.wait(
        lambda status: jubilant.all_active(
            status, HAPROXY_APP_NAME, APP_NAME, INGRESS_REQUIRER_APP_NAME
        ),
        error=jubilant.any_error,
    )
    addr = str(get_unit_addresses(juju, HAPROXY_APP_NAME)[0])
    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, addr)])

    response = session.get(f"http://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert response.history[0].status_code == 302
    juju.config(APP_NAME, {"allow-http": True})
    juju.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, APP_NAME),
        error=jubilant.any_error,
    )

    response = session.get(f"http://{MOCK_HAPROXY_HOSTNAME}", verify=False, timeout=30)
    assert "Apache2 Default Page" in response.text
