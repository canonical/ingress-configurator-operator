# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the charm in integrator mode."""

import json

import jubilant

from ..conftest import CERTIFICATES_APP_NAME, MOCK_HAPROXY_HOSTNAME


def test_action_get_proxied_endpoints_nominal(
    juju_lxd: jubilant.Juju, application: str, haproxy: str, ingress_requirer: str
):
    """Test the charm actions in integrator mode.

    Args:
        juju_lxd: Jubilant Juju instance for the LXD model.
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        ingress_requirer: Any charm running an apache webserver.
    """
    juju_lxd.config(
        haproxy,
        {"external-hostname": f"{MOCK_HAPROXY_HOSTNAME}"},
    )
    juju_lxd.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")

    juju_lxd.wait(
        lambda status: jubilant.all_agents_idle(
            status, haproxy, application, ingress_requirer, CERTIFICATES_APP_NAME
        ),
        error=jubilant.any_error,
    )
    unit = next(iter(juju_lxd.status().apps[application].units))

    # Test with no configured hostname on ingress configurator
    task = juju_lxd.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{MOCK_HAPROXY_HOSTNAME}/"]'}, task.results

    # Test with configured hostname on ingress
    hostname = "test.ingress.hostname"
    juju_lxd.config(
        application,
        {"hostname": hostname},
    )
    juju_lxd.wait(
        lambda status: jubilant.all_agents_idle(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    task = juju_lxd.run(unit, "get-proxied-endpoints")
    assert task.results == {"endpoints": f'["https://{hostname}/"]'}, task.results

    # Test with configured additional_hostnames on ingress
    additional_hostnames = [
        "test1.ingress.addition_hostname",
        "test2.ingress.addition_hostname",
    ]
    juju_lxd.config(
        application,
        {"additional-hostnames": ",".join(additional_hostnames)},
    )
    juju_lxd.wait(
        lambda status: jubilant.all_agents_idle(status, haproxy, application, ingress_requirer),
        error=jubilant.any_error,
    )
    task = juju_lxd.run(unit, "get-proxied-endpoints")

    endpoints = set(json.loads(task.results["endpoints"]))
    assert endpoints == {f"https://{h}/" for h in [hostname, *additional_hostnames]}, task.results
