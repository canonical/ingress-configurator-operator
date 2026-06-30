# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""End-to-end integration test exercising multiple gateway-route relations on one gateway.

A headline goal of the gateway-api redesign is supporting multiple ``gateway-route`` relations on
a single gateway-api-integrator, with one ingress-configurator per relation. This test proves
that by deploying two ingress-configurator instances against the same gateway at once:

    flask-k8s (closed)   ──ingress──▶  configurator-closed  ─┐  gateway-route
    any-charm-k8s (open) ──ingress──▶  configurator-open    ─┘──────────────▶ gateway-api-integrator
                                                                                       │
                                                                               Gateway + HTTPRoutes
                                                                               (one LoadBalancer address)

Each configurator is exposed on a distinct hostname. The test asserts that:
  * both modes (closed-ports adapter and open-ports adapter) route simultaneously through the
    single shared gateway, and
  * per-relation config (a distinct additional hostname plus a path restriction) takes effect
    independently for each, with no cross-relation interference.
"""

import logging
from typing import NamedTuple

import jubilant
import pytest

from .conftest import (
    ADDITIONAL_HOSTNAME_CLOSED,
    ADDITIONAL_HOSTNAME_OPEN,
    GATEWAY_BACKEND_OPEN_BODY,
    GATEWAY_BACKEND_OPEN_PATH,
    GATEWAY_CONFIGURATOR_CLOSED,
    GATEWAY_CONFIGURATOR_OPEN,
    HOSTNAME_CLOSED,
    HOSTNAME_OPEN,
    INGRESS_BACKEND_PORT,
    deploy_ingress_configurator_for_gateway_route,
)
from .helper import (
    assert_gateway_response,
    get_gateway_address,
)

logger = logging.getLogger(__name__)

# Path and body served by the open-ports backend — must match config.json injected
# into the backend-open deployment (defined in conftest).
BACKEND_PORT = INGRESS_BACKEND_PORT
BACKEND_PATH = GATEWAY_BACKEND_OPEN_PATH
BACKEND_BODY = GATEWAY_BACKEND_OPEN_BODY


class GatewayStack(NamedTuple):
    """All deployed app names and the shared gateway address for the multi-relation test."""

    gateway_api_integrator: str
    backend_closed: str
    backend_open: str
    configurator_closed: str
    configurator_open: str


@pytest.fixture(scope="module", name="multi_relation_gateway_stack")
def multi_relation_gateway_stack_fixture(
    juju_k8s: jubilant.Juju,
    gateway_api_integrator: str,
    backend_closed: str,
    backend_open: str,
    charm: str,
) -> GatewayStack:
    """Deploy and configure two configurators on one gateway and return its address.

    Deploys one ingress-configurator per adapter variant (closed-ports and open-ports) against
    the shared gateway-api-integrator, wires the ingress relations, configures each on a distinct
    hostname with a path restriction, and waits for the whole stack to settle.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: gateway-api-integrator (gateway-route provider) app name.
        backend_closed: flask-k8s backend with its port closed (adapter, closed-ports branch).
        backend_open: any-charm-k8s backend that opens its port (adapter, open-ports branch).
        charm: Path to the packed ingress-configurator charm.

    Returns:
        The gateway stack with the LoadBalancer address and all deployed app names.
    """
    # Deploy one configurator per mode with its config inline.
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s,
        charm,
        GATEWAY_CONFIGURATOR_CLOSED,
        gateway_api_integrator,
        config={
            "hostname": HOSTNAME_CLOSED,
            "additional-hostnames": ADDITIONAL_HOSTNAME_CLOSED,
            "paths": BACKEND_PATH,
        },
    )
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s,
        charm,
        GATEWAY_CONFIGURATOR_OPEN,
        gateway_api_integrator,
        config={
            "hostname": HOSTNAME_OPEN,
            "additional-hostnames": ADDITIONAL_HOSTNAME_OPEN,
            "paths": BACKEND_PATH,
        },
    )
    juju_k8s.integrate(f"{backend_closed}:ingress", f"{GATEWAY_CONFIGURATOR_CLOSED}:ingress")
    juju_k8s.integrate(f"{backend_open}:ingress", f"{GATEWAY_CONFIGURATOR_OPEN}:ingress")

    # Wait for the whole stack to settle.
    all_apps = (
        gateway_api_integrator,
        GATEWAY_CONFIGURATOR_CLOSED,
        GATEWAY_CONFIGURATOR_OPEN,
        backend_closed,
        backend_open,
    )
    juju_k8s.wait(
        lambda status: jubilant.all_active(status, *all_apps),
        error=jubilant.any_error,
    )

    return GatewayStack(
        gateway_api_integrator=gateway_api_integrator,
        backend_closed=backend_closed,
        backend_open=backend_open,
        configurator_closed=GATEWAY_CONFIGURATOR_CLOSED,
        configurator_open=GATEWAY_CONFIGURATOR_OPEN,
    )


@pytest.mark.abort_on_fail
def test_gateway_route_multiple_relations(
    juju_k8s: jubilant.Juju, multi_relation_gateway_stack: GatewayStack
):
    """Route two ingress-configurator instances through one gateway simultaneously.

    Args:
        multi_relation_gateway_stack: Shared gateway stack with all deployed app names
            and the gateway address.
    """
    gateway_address = get_gateway_address(
        juju_k8s, multi_relation_gateway_stack.gateway_api_integrator
    )

    # --- Closed-ports adapter (flask-k8s, is_port_open=False) ---
    # The configurator creates a selector Service targeting the backend pod; no body assertion
    # since flask-k8s serves its own response.
    logger.info(
        "checking closed-ports routing (%s, %s)", HOSTNAME_CLOSED, ADDITIONAL_HOSTNAME_CLOSED
    )
    assert_gateway_response(gateway_address, HOSTNAME_CLOSED, BACKEND_PATH, expected_status=200)
    assert_gateway_response(gateway_address, HOSTNAME_CLOSED, "/", expected_status=404)
    assert_gateway_response(
        gateway_address, ADDITIONAL_HOSTNAME_CLOSED, BACKEND_PATH, expected_status=200
    )
    assert_gateway_response(gateway_address, ADDITIONAL_HOSTNAME_CLOSED, "/", expected_status=404)

    # --- Open-ports adapter (any-charm-k8s, is_port_open=True) ---
    # The configurator routes directly to the pod IP; assert BACKEND_BODY to prove traffic
    # reaches this specific backend rather than any other 200 source.
    logger.info("checking open-ports routing (%s, %s)", HOSTNAME_OPEN, ADDITIONAL_HOSTNAME_OPEN)
    assert_gateway_response(
        gateway_address,
        HOSTNAME_OPEN,
        BACKEND_PATH,
        expected_status=200,
        body_contains=BACKEND_BODY,
    )
    assert_gateway_response(gateway_address, HOSTNAME_OPEN, "/", expected_status=404)
    assert_gateway_response(
        gateway_address,
        ADDITIONAL_HOSTNAME_OPEN,
        BACKEND_PATH,
        expected_status=200,
        body_contains=BACKEND_BODY,
    )
    assert_gateway_response(gateway_address, ADDITIONAL_HOSTNAME_OPEN, "/", expected_status=404)
