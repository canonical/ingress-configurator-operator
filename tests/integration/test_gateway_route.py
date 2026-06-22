# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""End-to-end integration test exercising multiple gateway-route relations on one gateway.

A headline goal of the gateway-api redesign is supporting multiple ``gateway-route`` relations on
a single gateway-api-integrator, with one ingress-configurator per relation. This test proves
that by deploying all three ingress-configurator modes against the same gateway at once:

    flask-k8s (closed)      ──ingress──▶  configurator-closed      ─┐
    any-charm-k8s (open)    ──ingress──▶  configurator-open        ─┤  gateway-route
    flask-k8s (IP only)     ─(config)──▶  configurator-integrator  ─┘──────────────▶ gateway-api-integrator
                                                                                              │
                                                                                      Gateway + HTTPRoutes
                                                                                      (one LoadBalancer address)

Each configurator is exposed on a distinct hostname. The test asserts that:
  * each mode leaves its distinct Kubernetes fingerprint (closed → selector Service present,
    open → selector Service absent, integrator → headless Service + EndpointSlice present),
  * all three relations route simultaneously through the single shared gateway, and
  * per-relation config (a distinct additional hostname plus a path restriction) takes effect
    independently for each, with no cross-relation interference.
"""

import logging

import jubilant
import pytest

from .conftest import (
    ADDITIONAL_HOSTNAME_CLOSED,
    ADDITIONAL_HOSTNAME_INTEGRATOR,
    ADDITIONAL_HOSTNAME_OPEN,
    GATEWAY_CONFIGURATOR_CLOSED,
    GATEWAY_CONFIGURATOR_INTEGRATOR,
    GATEWAY_CONFIGURATOR_OPEN,
    HOSTNAME_CLOSED,
    HOSTNAME_INTEGRATOR,
    HOSTNAME_OPEN,
    INGRESS_BACKEND_PORT,
    deploy_configurator,
)
from .helper import (
    assert_gateway_response,
    get_gateway_address,
    k8s_endpoint_slice_exists,
    k8s_service_exists,
)

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_gateway_route_multiple_relations(
    gateway_juju: jubilant.Juju,
    gateway_api_integrator: str,
    backend_closed: str,
    backend_open: str,
    backend_integrator: str,
    charm: str,
):
    """Route three ingress-configurator instances through one gateway simultaneously.

    Args:
        gateway_juju: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: gateway-api-integrator (gateway-route provider) app name.
        backend_closed: flask-k8s backend with its port closed (adapter, closed-ports branch).
        backend_open: any-charm-k8s backend that opens its port (adapter, open-ports branch).
        backend_integrator: flask-k8s backend referenced by IP only (integrator mode).
        charm: Path to the packed ingress-configurator charm.
    """
    # Deploy one configurator per mode against the shared gateway.
    deploy_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_CLOSED, gateway=gateway_api_integrator
    )
    deploy_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_OPEN, gateway=gateway_api_integrator
    )
    deploy_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_INTEGRATOR, gateway=gateway_api_integrator
    )
    gateway_juju.integrate(f"{backend_closed}:ingress", f"{GATEWAY_CONFIGURATOR_CLOSED}:ingress")
    gateway_juju.integrate(f"{backend_open}:ingress", f"{GATEWAY_CONFIGURATOR_OPEN}:ingress")

    primary_hostnames = {
        GATEWAY_CONFIGURATOR_CLOSED: HOSTNAME_CLOSED,
        GATEWAY_CONFIGURATOR_OPEN: HOSTNAME_OPEN,
        GATEWAY_CONFIGURATOR_INTEGRATOR: HOSTNAME_INTEGRATOR,
    }
    additional_hostnames = {
        GATEWAY_CONFIGURATOR_CLOSED: ADDITIONAL_HOSTNAME_CLOSED,
        GATEWAY_CONFIGURATOR_OPEN: ADDITIONAL_HOSTNAME_OPEN,
        GATEWAY_CONFIGURATOR_INTEGRATOR: ADDITIONAL_HOSTNAME_INTEGRATOR,
    }

    # The integrator configurator is driven by config only, so read its backend pod IP first.
    gateway_juju.wait(
        lambda status: any(unit.address for unit in status.apps[backend_integrator].units.values())
    )
    integrator_backend_address = next(
        unit.address
        for unit in gateway_juju.status().apps[backend_integrator].units.values()
        if unit.address
    )
    logger.info("integrator backend pod IP: %s", integrator_backend_address)
    gateway_juju.config(
        GATEWAY_CONFIGURATOR_CLOSED,
        {
            "hostname": HOSTNAME_CLOSED,
            "additional-hostnames": ADDITIONAL_HOSTNAME_CLOSED,
            "paths": "/restricted",
        },
    )
    gateway_juju.config(
        GATEWAY_CONFIGURATOR_OPEN,
        {
            "hostname": HOSTNAME_OPEN,
            "additional-hostnames": ADDITIONAL_HOSTNAME_OPEN,
            "paths": "/restricted",
        },
    )
    gateway_juju.config(
        GATEWAY_CONFIGURATOR_INTEGRATOR,
        {
            "backend-addresses": integrator_backend_address,
            "backend-ports": INGRESS_BACKEND_PORT,
            "hostname": HOSTNAME_INTEGRATOR,
            "additional-hostnames": ADDITIONAL_HOSTNAME_INTEGRATOR,
            "paths": "/restricted",
        },
    )

    # Apply all config at once, then wait for the whole stack to settle.
    all_apps = (
        gateway_api_integrator,
        GATEWAY_CONFIGURATOR_CLOSED,
        GATEWAY_CONFIGURATOR_OPEN,
        GATEWAY_CONFIGURATOR_INTEGRATOR,
        backend_closed,
        backend_open,
        backend_integrator,
    )
    gateway_juju.wait(
        lambda status: jubilant.all_active(status, *all_apps),
        error=jubilant.any_error,
    )

    gateway_address = get_gateway_address(gateway_juju, gateway_api_integrator)
    assert gateway_address, "gateway-api-integrator did not report a gateway address"
    logger.info("gateway address: %s", gateway_address)

    # Each mode leaves a distinct Kubernetes fingerprint.
    namespace = gateway_juju.model
    assert namespace is not None
    assert k8s_service_exists(namespace, f"{GATEWAY_CONFIGURATOR_CLOSED}-{backend_closed}"), (
        "closed-ports adapter must create a selector Service"
    )
    assert not k8s_service_exists(namespace, f"{GATEWAY_CONFIGURATOR_OPEN}-{backend_open}"), (
        "open-ports adapter must not create a selector Service"
    )
    assert k8s_service_exists(namespace, f"{GATEWAY_CONFIGURATOR_INTEGRATOR}-headless"), (
        "integrator must create a headless Service"
    )
    assert k8s_endpoint_slice_exists(namespace, f"{GATEWAY_CONFIGURATOR_INTEGRATOR}-headless"), (
        "integrator must create an EndpointSlice"
    )

    # Every relation routes through the shared gateway and its path restriction applies
    # independently: the restricted path returns 200, while "/" returns 404 per hostname.
    for configurator, primary in primary_hostnames.items():
        additional = additional_hostnames[configurator]
        logger.info("checking routing for %s (%s, %s)", configurator, primary, additional)
        assert_gateway_response(gateway_address, primary, "/restricted", expected_status=200)
        assert_gateway_response(gateway_address, primary, "/", expected_status=404)
        assert_gateway_response(gateway_address, additional, "/restricted", expected_status=200)
        assert_gateway_response(gateway_address, additional, "/", expected_status=404)
