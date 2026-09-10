# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for ingress-per-unit support in the ingress configurator charm."""

from typing import TYPE_CHECKING

import ops.testing
import pytest
import yaml

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
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            ),
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


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_happy_path_publishes_per_unit_urls(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit (2 units) + gateway-route with provider data, hostname set.
    act: config-changed.
    assert: Active; per-unit URLs published to the ingress-per-unit app databag.
    """
    state = ops.testing.State(
        leader=True,
        model=ops.testing.Model(name="testing"),
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data={
                    0: {
                        "model": "testing",
                        "name": "requirer/0",
                        "host": "requirer-0.local",
                        "port": "8080",
                    },
                    1: {
                        "model": "testing",
                        "name": "requirer/1",
                        "host": "requirer-1.local",
                        "port": "8080",
                    },
                },
            ),
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            ),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    ipu_app_data = out.get_relations("ingress-per-unit")[0].local_app_data
    published = yaml.safe_load(ipu_app_data["ingress"])
    assert published["requirer/0"]["url"] == "https://example.com/testing-requirer/0"
    assert published["requirer/1"]["url"] == "https://example.com/testing-requirer/1"


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_creates_pod_services_and_routes(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube,
):
    """
    arrange: ingress-per-unit (1 unit) + gateway-route.
    act: config-changed.
    assert: a pod-name-selector Service was applied for the unit.
    """
    state = ops.testing.State(
        leader=True,
        model=ops.testing.Model(name="testing"),
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data={
                    0: {
                        "model": "testing",
                        "name": "requirer/0",
                        "host": "requirer-0.local",
                        "port": "8080",
                    },
                },
            ),
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            ),
        ],
    )

    context_k8s.run(context_k8s.on.config_changed(), state)

    applied_services = [
        call.args[0]
        for call in mock_lightkube.apply.call_args_list
        if getattr(call.args[0], "kind", "") == "Service"
        or type(call.args[0]).__name__ == "Service"
    ]
    selectors = [svc.spec.selector for svc in applied_services if svc.spec and svc.spec.selector]
    assert {"statefulset.kubernetes.io/pod-name": "requirer-0"} in selectors


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_waiting_when_no_provider_data(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit ready but gateway-route provider data missing.
    act: config-changed.
    assert: WaitingStatus.
    """
    state = ops.testing.State(
        leader=True,
        model=ops.testing.Model(name="testing"),
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data={
                    0: {
                        "model": "testing",
                        "name": "requirer/0",
                        "host": "requirer-0.local",
                        "port": "8080",
                    },
                },
            ),
            ops.testing.Relation(endpoint="gateway-route"),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.WaitingStatus)


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_relation_broken_cleans_up(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube,
):
    """
    arrange: only gateway-route related (ingress-per-unit already gone).
    act: config-changed.
    assert: BlockedStatus asking for an ingress relation; stale-cleanup attempted.
    """
    state = ops.testing.State(
        leader=True,
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            )
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert mock_lightkube.list.called


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_ignores_paths_config(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit (1 unit) + gateway-route, with a `paths` config set.
    act: config-changed.
    assert: the published URL uses the provider-assigned /<model>-<unit_name> path,
        NOT the `paths` config value.
    """
    state = ops.testing.State(
        leader=True,
        model=ops.testing.Model(name="testing"),
        config={"hostname": "example.com", "paths": "/should-not-be-used"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data={
                    0: {
                        "model": "testing",
                        "name": "requirer/0",
                        "host": "requirer-0.local",
                        "port": "8080",
                    },
                },
            ),
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            ),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    published = yaml.safe_load(out.get_relations("ingress-per-unit")[0].local_app_data["ingress"])
    assert published["requirer/0"]["url"] == "https://example.com/testing-requirer/0"


@pytest.mark.usefixtures("mock_lightkube")
def test_ipu_cross_model_unit_blocks(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: ingress-per-unit unit reports a different model than the charm's.
    act: config-changed.
    assert: BlockedStatus (cross-model per-unit is unsupported).
    """
    state = ops.testing.State(
        leader=True,
        model=ops.testing.Model(name="testing"),
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress-per-unit",
                interface="ingress_per_unit",
                remote_app_name="requirer",
                remote_units_data={
                    0: {
                        "model": "other-model",
                        "name": "requirer/0",
                        "host": "requirer-0.local",
                        "port": "8080",
                    },
                },
            ),
            ops.testing.Relation(
                endpoint="gateway-route", remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA
            ),
        ],
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "ingress-per-unit" in out.unit_status.message
