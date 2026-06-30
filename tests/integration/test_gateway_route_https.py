# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""End-to-end integration tests for gateway-route enforced HTTPS with multiple relations.

Topology:

    self-signed-certificates ──certificates──▶ gateway-api-integrator (enforce-https=True)
                                                          ▲
    flask-k8s (backend-closed)  ──ingress──▶ configurator-closed ─┤ gateway-route
    any-charm-k8s (backend-open) ──ingress──▶ configurator-open  ─┘

The provider creates one per-hostname HTTPS Gateway listener per relation (one for
``HOSTNAME_CLOSED``, one for ``HOSTNAME_OPEN``). Each listener has its own ``hostname``
field, so Cilium can assign a distinct SNI match to each Envoy filter chain, avoiding
the "duplicate matcher" error that broke multi-relation HTTPS in the previous design.

This module tests two things:
1. **The regression**: with ≥ 2 HTTPS relations the gateway is reachable at all (not
   NACKed by Envoy due to duplicate filter-chain matches).
2. **Correct routing**: HTTP redirects to HTTPS and HTTPS reaches the backend for each
   of the two distinct hostnames.
"""

import logging
from typing import NamedTuple

import jubilant
import pytest

from .conftest import (
    CERTIFICATES_APP_NAME,
    GATEWAY_CERTIFICATES_CHANNEL,
    GATEWAY_CONFIGURATOR_CLOSED,
    GATEWAY_CONFIGURATOR_OPEN,
    HOSTNAME_CLOSED,
    HOSTNAME_OPEN,
    deploy_ingress_configurator_for_gateway_route,
)
from .helper import assert_gateway_response, get_gateway_address

logger = logging.getLogger(__name__)


class HTTPSGatewayStack(NamedTuple):
    """All deployed app names for the multi-relation enforced-HTTPS test."""

    gateway_api_integrator: str
    backend_closed: str
    backend_open: str
    configurator_closed: str
    configurator_open: str


@pytest.fixture(scope="module", name="multi_relation_https_stack")
def multi_relation_https_stack_fixture(
    juju_k8s: jubilant.Juju,
    gateway_api_integrator: str,
    backend_closed: str,
    backend_open: str,
    charm: str,
) -> HTTPSGatewayStack:
    """Deploy two ingress-configurators on one HTTPS gateway and wait for all Active.

    Enables ``enforce-https`` on the shared gateway, relates it to a TLS provider, then
    deploys one configurator per backend (closed-ports and open-ports) and wires their
    ``ingress`` relations.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: Shared gateway-route provider app name.
        backend_closed: flask-k8s backend (is_port_open=False).
        backend_open: any-charm-k8s backend (is_port_open=True).
        charm: Path to the packed ingress-configurator charm.

    Returns:
        Named tuple with all deployed app names.
    """
    juju_k8s.config(gateway_api_integrator, {"enforce-https": True})
    juju_k8s.deploy(charm=CERTIFICATES_APP_NAME, channel=GATEWAY_CERTIFICATES_CHANNEL)
    juju_k8s.integrate(
        f"{CERTIFICATES_APP_NAME}:certificates", f"{gateway_api_integrator}:certificates"
    )
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s,
        charm,
        GATEWAY_CONFIGURATOR_CLOSED,
        gateway_api_integrator,
        config={"hostname": HOSTNAME_CLOSED},
    )
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s,
        charm,
        GATEWAY_CONFIGURATOR_OPEN,
        gateway_api_integrator,
        config={"hostname": HOSTNAME_OPEN},
    )
    juju_k8s.integrate(f"{backend_closed}:ingress", f"{GATEWAY_CONFIGURATOR_CLOSED}:ingress")
    juju_k8s.integrate(f"{backend_open}:ingress", f"{GATEWAY_CONFIGURATOR_OPEN}:ingress")

    all_apps = (
        gateway_api_integrator,
        CERTIFICATES_APP_NAME,
        GATEWAY_CONFIGURATOR_CLOSED,
        GATEWAY_CONFIGURATOR_OPEN,
        backend_closed,
        backend_open,
    )
    juju_k8s.wait(
        lambda status: jubilant.all_active(status, *all_apps),
        error=jubilant.any_error,
    )

    return HTTPSGatewayStack(
        gateway_api_integrator=gateway_api_integrator,
        backend_closed=backend_closed,
        backend_open=backend_open,
        configurator_closed=GATEWAY_CONFIGURATOR_CLOSED,
        configurator_open=GATEWAY_CONFIGURATOR_OPEN,
    )


@pytest.mark.abort_on_fail
def test_gateway_route_https_enforced_multi_relation(
    juju_k8s: jubilant.Juju,
    multi_relation_https_stack: HTTPSGatewayStack,
):
    """Two HTTPS relations: HTTP redirects and HTTPS backend reach work for each hostname.

    This is the regression test for the Cilium/Envoy duplicate filter-chain bug.  With the
    old design (all certs on one hostname-less listener), Envoy NACKs the whole listener and
    both :80 and :443 become unreachable.  With the fix (one listener per hostname, each
    carrying its own ``hostname`` field), Envoy can distinguish chains by SNI and the gateway
    remains reachable.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        multi_relation_https_stack: Shared stack with gateway address and all app names.
    """
    gateway_address = get_gateway_address(
        juju_k8s, multi_relation_https_stack.gateway_api_integrator
    )
    assert gateway_address, "gateway-api-integrator did not report a gateway address"
    logger.info("gateway address: %s", gateway_address)

    for hostname in (HOSTNAME_CLOSED, HOSTNAME_OPEN):
        logger.info("checking enforced-HTTPS routing for %s", hostname)

        # HTTP must issue a 301 redirect to HTTPS.
        redirect = assert_gateway_response(
            gateway_address,
            hostname,
            "/",
            scheme="http",
            expected_status=301,
            allow_redirects=False,
        )
        location = redirect.headers.get("location", "")
        assert location.startswith("https://"), (
            f"expected an HTTPS redirect Location for {hostname}, got {location!r}"
        )

        # HTTPS must reach the backend (SNI carries the hostname; self-signed cert not verified).
        assert_gateway_response(
            gateway_address,
            hostname,
            "/",
            scheme="https",
            expected_status=200,
        )
