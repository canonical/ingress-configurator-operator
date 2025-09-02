# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""
import json

import jubilant

from .conftest import MOCK_HAPROXY_HOSTNAME


def test_action_get_proxied_endpoints_nominal(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    ingress_requirer: str,
):
    """Test the charm actions in integrator mode.

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
    """
    juju.config(
        haproxy,
        {"external-hostname": f"{MOCK_HAPROXY_HOSTNAME}"},
    )
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")

    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    unit = next(iter(juju.status().apps[application].units))

    # Test with no configured hostname on ingress configurator
    task = juju.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{MOCK_HAPROXY_HOSTNAME}/"]'}, task.results

    # Test with configured hostname on ingress
    hostname = "test.ingress.hostname"
    juju.config(
        application,
        {"hostname": hostname},
    )
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    task = juju.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{hostname}/"]'}, task.results

    # Test with configured additional_hostnames on ingress
    additional_hostnames = ["test1.ingress.addition_hostname", "test2.ingress.addition_hostname"]
    juju.config(
        application,
        {"additional-hostnames": ",".join(additional_hostnames)},
    )
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    task = juju.run(unit, "get-proxied-endpoints")

    endpoints = set(json.loads(task.results["endpoints"]))
    assert endpoints == {f"https://{h}/" for h in [hostname] + additional_hostnames}, task.results
