# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

import json

import jubilant
import pytest

from .conftest import (
    APP_NAME,
    HAPROXY_APP_NAME,
    INGRESS_REQUIRER_APP_NAME,
    MOCK_HAPROXY_HOSTNAME,
    deploy_ingress_requirer,
    deploy_with_haproxy,
)


@pytest.mark.juju_setup
def test_deploy_with_haproxy(juju: jubilant.Juju, charm: str):
    deploy_with_haproxy(juju, charm)


@pytest.mark.juju_setup
def test_deploy_ingress_requirer(juju: jubilant.Juju):
    deploy_ingress_requirer(juju)


def test_action_get_proxied_endpoints_nominal(juju: jubilant.Juju):
    """Test the charm actions in integrator mode."""
    juju.config(
        HAPROXY_APP_NAME,
        {"external-hostname": f"{MOCK_HAPROXY_HOSTNAME}"},
    )
    juju.integrate(f"{HAPROXY_APP_NAME}:haproxy-route", f"{APP_NAME}:haproxy-route")

    apps = (HAPROXY_APP_NAME, APP_NAME, INGRESS_REQUIRER_APP_NAME)
    juju.wait(lambda status: jubilant.all_active(status, *apps), error=jubilant.any_error)
    unit = next(iter(juju.status().apps[APP_NAME].units))

    # Test with no configured hostname on ingress configurator
    task = juju.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{MOCK_HAPROXY_HOSTNAME}/"]'}, task.results

    # Test with configured hostname on ingress
    hostname = "test.ingress.hostname"
    juju.config(
        APP_NAME,
        {"hostname": hostname},
    )
    juju.wait(lambda status: jubilant.all_active(status, *apps), error=jubilant.any_error)
    task = juju.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{hostname}/"]'}, task.results

    # Test with configured additional_hostnames on ingress
    additional_hostnames = ["test1.ingress.addition_hostname", "test2.ingress.addition_hostname"]
    juju.config(APP_NAME, {"additional-hostnames": ",".join(additional_hostnames)})
    juju.wait(lambda status: jubilant.all_active(status, *apps), error=jubilant.any_error)
    task = juju.run(unit, "get-proxied-endpoints")

    endpoints = set(json.loads(task.results["endpoints"]))
    assert endpoints == {f"https://{h}/" for h in [hostname, *additional_hostnames]}, task.results
