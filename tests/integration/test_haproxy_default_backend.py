# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the default-backend config option in integrator mode."""

import json

import jubilant
import pytest

from .conftest import CERTIFICATES_APP_NAME, get_unit_addresses


def _get_haproxy_route_application_data(juju: jubilant.Juju, units: list[str]) -> dict:
    """Return the haproxy-route application data published on the relation.

    The `show-unit` output has differed across Juju versions with respect to which side of
    the relation `application-data` corresponds to, so the data of every given unit is
    merged. This includes the requirer data required by this test regardless of the version.

    Args:
        juju: Jubilant juju fixture.
        units: Names of the units involved in the haproxy-route relation.

    Returns:
        The merged haproxy-route application data.
    """
    application_data: dict = {}
    for unit in units:
        unit_name = f"{unit}/0"
        unit_info = json.loads(juju.cli("show-unit", unit_name, "--format", "json"))[unit_name]
        for relation in unit_info["relation-info"]:
            if relation["endpoint"] == "haproxy-route":
                application_data.update(relation.get("application-data", {}))
    return application_data


@pytest.mark.abort_on_fail
def test_default_backend_config_option(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    any_charm_backend: str,
):
    """Configure the backend as the default landing page.

    Args:
        juju: Jubilant juju fixture.
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        any_charm_backend: Any charm running an apache webserver.
    """
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju.wait(
        lambda status: jubilant.all_agents_idle(
            status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
        ),
        error=jubilant.any_error,
    )
    backend_addresses = ",".join(
        [str(address) for address in get_unit_addresses(juju, any_charm_backend)]
    )
    juju.config(
        app=application,
        values={
            "backend-addresses": backend_addresses,
            "backend-ports": 80,
            "default-backend": True,
        },
    )
    juju.wait(
        lambda status: (
            jubilant.all_active(
                status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
            )
            and jubilant.all_agents_idle(
                status, haproxy, application, any_charm_backend, CERTIFICATES_APP_NAME
            )
        ),
        error=jubilant.any_error,
    )
    application_data = _get_haproxy_route_application_data(juju, [haproxy, application])
    assert application_data.get("default_backend") == "true"
