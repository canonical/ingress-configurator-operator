# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""End-to-end integration test for gateway-route enforced HTTPS (TLS termination).

Topology (single Kubernetes model):

    self-signed-certificates ──certificates──▶ gateway-api-integrator (enforce-https=True)
                                                          ▲
    flask-k8s (backend) ──ingress──▶ ingress-configurator ┘ gateway-route
                                                          │
                                                  Gateway (HTTP + HTTPS listeners) + HTTPRoutes

HTTPS/TLS termination itself is owned and already covered by gateway-api-integrator's own tests.
What this test covers from the ingress-configurator side is this charm's enforced-mode HTTPRoute
generation: when the provider reports ``https_mode=enforced`` ingress-configurator must create an
HTTP route that issues a 301 redirect to HTTPS *and* an HTTPS route that reaches the backend.
"""

import logging

import jubilant
import pytest

from .conftest import (
    CERTIFICATES_APP_NAME,
    GATEWAY_CERTIFICATES_CHANNEL,
    GATEWAY_CONFIGURATOR_CLOSED,
    HOSTNAME_CLOSED,
    deploy_ingress_configurator_for_gateway_route,
)
from .helper import get_gateway_address, wait_for_gateway_response

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
def test_gateway_route_https_enforced(
    juju_k8s: jubilant.Juju,
    gateway_api_integrator: str,
    backend_closed: str,
    charm: str,
):
    """Enforced HTTPS: HTTP is redirected to HTTPS and the HTTPS route reaches the backend.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: gateway-api-integrator (gateway-route provider) app name.
        backend_closed: flask-k8s backend workload app name.
        charm: Path to the packed ingress-configurator charm.
    """
    # Enforce HTTPS, relate the gateway to a TLS provider, and wire the configurator to the backend.
    juju_k8s.config(gateway_api_integrator, {"enforce-https": True})
    juju_k8s.deploy(charm=CERTIFICATES_APP_NAME, channel=GATEWAY_CERTIFICATES_CHANNEL)
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s, charm, GATEWAY_CONFIGURATOR_CLOSED, gateway_api_integrator
    )
    juju_k8s.integrate(
        f"{CERTIFICATES_APP_NAME}:certificates", f"{gateway_api_integrator}:certificates"
    )
    juju_k8s.integrate(f"{backend_closed}:ingress", f"{GATEWAY_CONFIGURATOR_CLOSED}:ingress")
    juju_k8s.config(GATEWAY_CONFIGURATOR_CLOSED, {"hostname": HOSTNAME_CLOSED})

    juju_k8s.wait(
        lambda status: jubilant.all_active(
            status,
            gateway_api_integrator,
            CERTIFICATES_APP_NAME,
            GATEWAY_CONFIGURATOR_CLOSED,
            backend_closed,
        ),
        error=jubilant.any_error,
    )

    gateway_address = get_gateway_address(juju_k8s, gateway_api_integrator)
    assert gateway_address, "gateway-api-integrator did not report a gateway address"
    logger.info("gateway address: %s", gateway_address)

    # HTTP is redirected to HTTPS (do not follow the redirect so the 301 and Location are visible).
    redirect = wait_for_gateway_response(
        gateway_address,
        HOSTNAME_CLOSED,
        "/",
        scheme="http",
        expected_status=301,
        allow_redirects=False,
    )
    location = redirect.headers.get("location", "")
    assert location.startswith("https://"), (
        f"expected an HTTPS redirect Location, got {location!r}"
    )

    # The HTTPS route reaches the backend (SNI carries the hostname; self-signed cert not verified).
    wait_for_gateway_response(
        gateway_address,
        HOSTNAME_CLOSED,
        "/",
        scheme="https",
        expected_status=200,
    )
