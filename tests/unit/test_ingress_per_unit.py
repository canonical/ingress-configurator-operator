# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for ingress-per-unit support in the ingress configurator charm."""

from typing import TYPE_CHECKING

import ops.testing
import pytest

if TYPE_CHECKING:
    from charm import IngressConfiguratorCharm

IPU_REMOTE_UNITS_DATA = {
    0: {"model": "testing", "name": "requirer/0", "host": "requirer-0.local", "port": "8080"},
}

GATEWAY_ROUTE_PROVIDER_DATA = {
    "gateway_name": '"my-gateway"',
    "gateway_model": '"gateway-model"',
    "https_mode": '"enforced"',
}


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_without_gateway_route_blocks(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit related but no gateway-route.
    act: config-changed.
    assert: BlockedStatus explaining gateway-route is required.
    """
    state = ops.testing.State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data=IPU_REMOTE_UNITS_DATA,
            ),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "gateway-route" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_with_ingress_relation_blocks(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: both ingress (per-app) and ingress-per-unit related.
    act: config-changed.
    assert: BlockedStatus (mutually exclusive).
    """
    state = ops.testing.State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data={
                    "model": '"testing"',
                    "name": '"requirer"',
                    "port": "8080",
                    "is_port_open": "true",
                },
                remote_units_data={0: {"host": '"x"', "ip": '"10.0.0.1"'}},
            ),
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data=IPU_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "ingress-per-unit" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_with_haproxy_route_blocks(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit + haproxy-route related.
    act: config-changed.
    assert: BlockedStatus (only gateway-route supports ingress-per-unit).
    """
    state = ops.testing.State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data=IPU_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(endpoint="haproxy-route", interface="haproxy-route"),
        ],
    )

    out = context_machine.run(context_machine.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "gateway-route" in out.unit_status.message
