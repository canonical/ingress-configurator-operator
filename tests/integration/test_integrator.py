# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

"""Test the charm in integrator mode."""

import jubilant


def test_integrator(juju: jubilant.Juju, application: str, haproxy: str):
    """_summary_

    Args:
        juju: Jubilant juju fixture
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
    """
    juju.integrate("haproxy:haproxy-route", f"{application}:haproxy-route")
    juju.config(app=application, values={"backend_address": "10.0.0.1", "backend_port": 80})
    juju.wait(
        lambda status: jubilant.all_active(status, haproxy, application), error=jubilant.any_error
    )
