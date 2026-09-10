# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""End-to-end integration test for ingress-per-unit via gateway-route.

A single ingress-configurator forwards an ``ingress-per-unit`` relation to a shared
gateway-api-integrator over ``gateway-route``. Each requirer unit gets its own URL
(``/<model>-<unit_name>``) backed by a per-unit Service (pod-name selector) and HTTPRoute:

    ipu-requirer/0 ─┐                                   ┌─ /<model>-ipu-requirer/0
    ipu-requirer/1 ─┴─ingress-per-unit─▶ configurator ─┤   gateway-route ─▶ gateway-api-integrator
                                                        └─ /<model>-ipu-requirer/1

Each requirer unit serves its own unit name, so the test proves that each per-unit path
routes to the matching unit and not to any other.
"""

import logging

import jubilant
import pytest

from .conftest import (
    IPU_CONFIGURATOR_APP_NAME,
    IPU_HOSTNAME,
    deploy_ingress_configurator_for_gateway_route,
)
from .helper import assert_gateway_response, get_gateway_address

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="ipu_stack")
def ipu_stack_fixture(
    juju_k8s: jubilant.Juju,
    gateway_api_integrator: str,
    ingress_per_unit_requirer: str,
    charm: str,
) -> str:
    """Wire a configurator to the gateway and the ingress-per-unit requirer; wait for active.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        gateway_api_integrator: gateway-api-integrator (gateway-route provider) app name.
        ingress_per_unit_requirer: The 2-unit ingress-per-unit requirer app name.
        charm: Path to the packed ingress-configurator charm.

    Returns:
        The gateway-api-integrator app name (used to resolve the gateway address).
    """
    deploy_ingress_configurator_for_gateway_route(
        juju_k8s,
        charm,
        IPU_CONFIGURATOR_APP_NAME,
        gateway_api_integrator,
        config={"hostname": IPU_HOSTNAME},
    )
    juju_k8s.integrate(
        f"{ingress_per_unit_requirer}:require-ingress-per-unit",
        f"{IPU_CONFIGURATOR_APP_NAME}:ingress-per-unit",
    )
    all_apps = (gateway_api_integrator, IPU_CONFIGURATOR_APP_NAME, ingress_per_unit_requirer)
    juju_k8s.wait(
        lambda status: jubilant.all_active(status, *all_apps),
        error=jubilant.any_error,
    )
    return gateway_api_integrator


@pytest.mark.abort_on_fail
def test_ingress_per_unit(
    juju_k8s: jubilant.Juju,
    ipu_stack: str,
    ingress_per_unit_requirer: str,
    k8s_model: str,
):
    """Route each requirer unit through the shared gateway on its own per-unit path.

    Args:
        juju_k8s: Jubilant Juju instance for the Kubernetes model.
        ipu_stack: The gateway-api-integrator app name (gateway address source).
        ingress_per_unit_requirer: The 2-unit ingress-per-unit requirer app name.
        k8s_model: The Kubernetes model name (used to build the per-unit path).
    """
    gateway_address = get_gateway_address(juju_k8s, ipu_stack)

    for unit_number in (0, 1):
        unit_name = f"{ingress_per_unit_requirer}/{unit_number}"
        per_unit_path = f"/{k8s_model}-{unit_name}"
        logger.info("checking per-unit routing for %s at %s", unit_name, per_unit_path)
        assert_gateway_response(
            gateway_address,
            IPU_HOSTNAME,
            per_unit_path,
            expected_status=200,
            body_contains=unit_name,
        )
