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
  * all three modes (closed-ports adapter, open-ports adapter, integrator) route simultaneously
    through the single shared gateway, and
  * per-relation config (a distinct additional hostname plus a path restriction) takes effect
    independently for each, with no cross-relation interference.
"""

import json
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
    deploy_gateway_route_configurator,
)
from .helper import (
    get_gateway_address,
    wait_for_gateway_response,
)

logger = logging.getLogger(__name__)

# Port, path and body served by the open-ports backend. Passed to the charm via RPC so
# tests can assert the body to prove traffic genuinely reaches this backend.
BACKEND_PORT = 80
BACKEND_PATH = "/api/v1"
BACKEND_BODY = "ok from open-ports backend"


@pytest.fixture(scope="module", name="multi_relation_gateway_address")
def multi_relation_gateway_address_fixture(
    gateway_juju: jubilant.Juju,
    gateway_api_integrator: str,
    backend_closed: str,
    backend_open: str,
    backend_integrator: str,
    charm: str,
) -> str:
    """Deploy and configure three configurators on one gateway and return its address.

    Deploys one ingress-configurator per mode (closed-ports adapter, open-ports adapter and
    integrator) against the shared gateway-api-integrator, wires the relations, configures each
    on a distinct hostname with a path restriction, and waits for the whole stack to settle.

    Args:
        gateway_juju: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: gateway-api-integrator (gateway-route provider) app name.
        backend_closed: flask-k8s backend with its port closed (adapter, closed-ports branch).
        backend_open: any-charm-k8s backend that opens its port (adapter, open-ports branch).
        backend_integrator: flask-k8s backend referenced by IP only (integrator mode).
        charm: Path to the packed ingress-configurator charm.

    Returns:
        The gateway LoadBalancer address shared by all three relations.
    """
    # Deploy one configurator per mode against the shared gateway.
    deploy_gateway_route_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_CLOSED, gateway_api_integrator
    )
    deploy_gateway_route_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_OPEN, gateway_api_integrator
    )
    deploy_gateway_route_configurator(
        gateway_juju, charm, GATEWAY_CONFIGURATOR_INTEGRATOR, gateway_api_integrator
    )
    gateway_juju.integrate(f"{backend_closed}:ingress", f"{GATEWAY_CONFIGURATOR_CLOSED}:ingress")
    gateway_juju.integrate(f"{backend_open}:ingress", f"{GATEWAY_CONFIGURATOR_OPEN}:ingress")

    # Configure the open-ports backend to serve BACKEND_BODY at BACKEND_PATH via RPC.
    # We wait for the unit to be reachable before calling RPC.
    gateway_juju.wait(lambda status: jubilant.all_agents_idle(status, backend_open))
    gateway_juju.run(
        f"{backend_open}/0",
        "rpc",
        {"method": "start_server", "args": json.dumps([BACKEND_PORT, BACKEND_PATH, BACKEND_BODY])},
    )

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
            "paths": BACKEND_PATH,
        },
    )
    gateway_juju.config(
        GATEWAY_CONFIGURATOR_OPEN,
        {
            "hostname": HOSTNAME_OPEN,
            "additional-hostnames": ADDITIONAL_HOSTNAME_OPEN,
            "paths": BACKEND_PATH,
        },
    )
    gateway_juju.config(
        GATEWAY_CONFIGURATOR_INTEGRATOR,
        {
            "backend-addresses": integrator_backend_address,
            "backend-ports": INGRESS_BACKEND_PORT,
            "hostname": HOSTNAME_INTEGRATOR,
            "additional-hostnames": ADDITIONAL_HOSTNAME_INTEGRATOR,
            "paths": BACKEND_PATH,
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
    return gateway_address


@pytest.mark.abort_on_fail
def test_gateway_route_multiple_relations(multi_relation_gateway_address: str):
    """Route three ingress-configurator instances through one gateway simultaneously.

    Args:
        multi_relation_gateway_address: Shared gateway address with all three relations
            deployed and configured.
    """
    gateway_address = multi_relation_gateway_address

    # --- Closed-ports adapter (flask-k8s, is_port_open=False) ---
    # The configurator creates a selector Service targeting the backend pod; no body assertion
    # since flask-k8s serves its own response.
    logger.info(
        "checking closed-ports routing (%s, %s)", HOSTNAME_CLOSED, ADDITIONAL_HOSTNAME_CLOSED
    )
    wait_for_gateway_response(gateway_address, HOSTNAME_CLOSED, BACKEND_PATH, expected_status=200)
    wait_for_gateway_response(gateway_address, HOSTNAME_CLOSED, "/", expected_status=404)
    wait_for_gateway_response(
        gateway_address, ADDITIONAL_HOSTNAME_CLOSED, BACKEND_PATH, expected_status=200
    )
    wait_for_gateway_response(
        gateway_address, ADDITIONAL_HOSTNAME_CLOSED, "/", expected_status=404
    )

    # --- Open-ports adapter (any-charm-k8s, is_port_open=True) ---
    # The configurator routes directly to the pod IP; assert BACKEND_BODY to prove traffic
    # reaches this specific backend rather than any other 200 source.
    logger.info("checking open-ports routing (%s, %s)", HOSTNAME_OPEN, ADDITIONAL_HOSTNAME_OPEN)
    wait_for_gateway_response(
        gateway_address,
        HOSTNAME_OPEN,
        BACKEND_PATH,
        expected_status=200,
        body_contains=BACKEND_BODY,
    )
    wait_for_gateway_response(gateway_address, HOSTNAME_OPEN, "/", expected_status=404)
    wait_for_gateway_response(
        gateway_address,
        ADDITIONAL_HOSTNAME_OPEN,
        BACKEND_PATH,
        expected_status=200,
        body_contains=BACKEND_BODY,
    )
    wait_for_gateway_response(gateway_address, ADDITIONAL_HOSTNAME_OPEN, "/", expected_status=404)

    # --- Integrator mode (config-driven backend IP, no ingress relation) ---
    # The configurator creates a headless Service + EndpointSlice pointing at the backend pod IP.
    logger.info(
        "checking integrator routing (%s, %s)", HOSTNAME_INTEGRATOR, ADDITIONAL_HOSTNAME_INTEGRATOR
    )
    wait_for_gateway_response(
        gateway_address, HOSTNAME_INTEGRATOR, BACKEND_PATH, expected_status=200
    )
    wait_for_gateway_response(gateway_address, HOSTNAME_INTEGRATOR, "/", expected_status=404)
    wait_for_gateway_response(
        gateway_address, ADDITIONAL_HOSTNAME_INTEGRATOR, BACKEND_PATH, expected_status=200
    )
    wait_for_gateway_response(
        gateway_address, ADDITIONAL_HOSTNAME_INTEGRATOR, "/", expected_status=404
    )
