# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

from typing import Callable

import jubilant
import pytest
from requests import Session

from .conftest import (
    ANY_CHARM_APP_NAME,
    APP_NAME,
    HAPROXY_APP_NAME,
    MOCK_HAPROXY_HOSTNAME,
    deploy_any_charm_backend,
    deploy_with_haproxy,
    get_unit_addresses,
)


@pytest.mark.juju_setup
def test_deploy_with_haproxy(juju: jubilant.Juju, charm: str):
    deploy_with_haproxy(juju, charm)


@pytest.mark.juju_setup
def test_deploy_any_charm_backend(juju: jubilant.Juju):
    deploy_any_charm_backend(juju)


def test_config_hostnames_and_paths(juju: jubilant.Juju, http_session: Callable[..., Session]):
    """Test the charm configuration in integrator mode."""
    juju.integrate(f"{HAPROXY_APP_NAME}:haproxy-route", f"{APP_NAME}:haproxy-route")
    backend_addresses = ",".join(
        [str(address) for address in get_unit_addresses(juju, ANY_CHARM_APP_NAME)]
    )
    juju.config(
        app=APP_NAME,
        values={
            "backend-addresses": backend_addresses,
            "backend-ports": 80,
            "paths": "/api/v1,/api/v2",
        },
    )
    juju.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, APP_NAME, ANY_CHARM_APP_NAME),
        error=jubilant.any_error,
    )

    haproxy_address = str(get_unit_addresses(juju, HAPROXY_APP_NAME)[0])
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

    juju.config(
        app=APP_NAME,
        values={
            "paths": "/api/v1",
            "hostname": f"api.{MOCK_HAPROXY_HOSTNAME}",
            "additional-hostnames": f"api2.{MOCK_HAPROXY_HOSTNAME},api3.{MOCK_HAPROXY_HOSTNAME}",
        },
    )
    juju.wait(
        lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, APP_NAME, ANY_CHARM_APP_NAME),
        error=jubilant.any_error,
    )

    for subdomain in ["api", "api2", "api3"]:
        response = session.get(
            f"https://{subdomain}.{MOCK_HAPROXY_HOSTNAME}/api/v1/", timeout=30, verify=False
        )
        assert response.status_code == 200 and "v1 ok!" in response.text
