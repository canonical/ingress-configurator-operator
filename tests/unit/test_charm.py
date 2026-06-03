# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

import json
from itertools import combinations
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock

import ops.testing
import pytest

from state.charm_state import InvalidStateError
from state.haproxy_route import HaproxyRouteState

if TYPE_CHECKING:
    from charm import IngressConfiguratorCharm


def test_config_changed_invalid_state(
    monkeypatch: pytest.MonkeyPatch,
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare some state with invalid backend-addresses.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    monkeypatch.setattr(HaproxyRouteState, "from_charm", MagicMock(side_effect=InvalidStateError))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus()


def test_config_changed_ingress_relation_not_ready(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare state with haproxy-route and an ingress relation whose requirer
        hasn't populated the databag yet (empty remote app data).
    act: trigger a config-changed event.
    assert: the hook succeeds (no exception) and the unit is blocked, not stuck in
        error state.
    """
    charm_state = ops.testing.State(
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation("ingress"),
        ],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("No valid mode detected.")


def test_config_changed_integrator(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare some valid state for an integrator.
    act: trigger a config changed event.
    assert: status is active.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,10.0.0.2", "backend-ports": "8080"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")


def test_protocol_propagated_to_haproxy(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """Valid protocol should be copied from config to haproxy-route relation"""
    in_ = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "80",
            "backend-protocol": "https",
        },
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), in_)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    assert out.get_relations("haproxy-route")[0].local_app_data == {
        "service": ANY,
        "ports": "[80]",
        "hosts": '["10.0.0.1"]',
        "protocol": '"https"',
    }


def test_external_grpc_port_propagated_to_haproxy(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """Valid external-grpc-port should be copied from config to haproxy-route relation"""
    in_ = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "80",
            "backend-protocol": "https",
            "external-grpc-port": 50051,
        },
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), in_)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    assert out.get_relations("haproxy-route")[0].local_app_data == {
        "service": ANY,
        "ports": "[80]",
        "hosts": '["10.0.0.1"]',
        "protocol": '"https"',
        "external_grpc_port": "50051",
    }


class TestGetProxiedEndpointAction:
    """Test "get-proxied-endpoints" Action"""

    @pytest.mark.parametrize(
        "endpoints",
        [
            pytest.param(
                '["https://fqdn.example/"]',
                id="single_endpoint",
            ),
            pytest.param(
                '["https://fqdn.example/", "https://fqdn2.example/"]',
                id="multiple_endpoints",
            ),
        ],
    )
    def test_nominal(
        self,
        endpoints: str,
        context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    ) -> None:
        """
        arrange: prepare state with haproxy relation
        act: trigger a get-proxied-endpoint action.
        assert: returns endpoint.
        """
        charm_state = ops.testing.State(
            config={"backend-addresses": "10.0.0.1", "backend-ports": "80"},
            relations=[
                ops.testing.Relation(
                    "haproxy-route",
                    remote_app_data={"endpoints": endpoints},
                ),
            ],
            leader=True,
            unit_status=ops.testing.ActiveStatus(),
        )
        context_machine.run(context_machine.on.action("get-proxied-endpoints"), charm_state)

        out = context_machine.action_results

        assert out == {"endpoints": endpoints}, "Unexpected action results."

    def test_no_endpoints(
        self,
        context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    ) -> None:
        """
        arrange: prepare state with haproxy relation
        act: trigger a get-proxied-endpoint action.
        assert: returns endpoint.
        """
        charm_state = ops.testing.State(
            config={"backend-addresses": "10.0.0.1", "backend-ports": "80"},
            relations=[
                ops.testing.Relation(
                    "haproxy-route",
                    remote_app_data={"endpoints": ""},
                ),
            ],
            leader=True,
            unit_status=ops.testing.ActiveStatus(),
        )
        context_machine.run(context_machine.on.action("get-proxied-endpoints"), charm_state)

        out = context_machine.action_results

        assert out == {"endpoints": {}}, "Unexpected action results."

    def test_no_haproxy_route_relation(
        self,
        context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    ) -> None:
        """
        arrange: prepare state with no haproxy relation.
        act: trigger a get-proxied-endpoint action.
        assert: Action returns empty dict.
        """
        charm_state = ops.testing.State(
            config={"backend-addresses": "10.0.0.1", "backend-ports": "80"},
            relations=[],
            leader=True,
            unit_status=ops.testing.ActiveStatus(),
        )
        with pytest.raises(ops.testing.ActionFailed) as excinfo:
            context_machine.run(context_machine.on.action("get-proxied-endpoints"), charm_state)
            assert str(excinfo.value) == "Missing haproxy-route relation."


def test_is_kubernetes_returns_true_when_no_machine_id(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: create a context without a machine_id (Kubernetes substrate)
    act: run any event and inspect the charm instance
    assert: is_kubernetes() returns True
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "80"},
        leader=True,
    )

    with context_k8s(context_k8s.on.config_changed(), state) as manager:
        assert manager.charm.is_kubernetes() is True


def test_is_kubernetes_returns_false_when_machine_id_is_set(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: create a context with a machine_id set (machine substrate)
    act: run any event and inspect the charm instance
    assert: is_kubernetes() returns False
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "80"},
        leader=True,
    )

    with context_machine(context_machine.on.config_changed(), state) as manager:
        assert manager.charm.is_kubernetes() is False


def test_haproxy_route(context_machine: ops.testing.Context["IngressConfiguratorCharm"]):
    """Valid protocol should be copied from config to haproxy-route-tcp relation."""
    in_ = ops.testing.State(
        config={
            "tcp-backend-addresses": "10.0.0.1",
            "tcp-frontend-port": 4000,
            "tcp-backend-port": 5000,
            "tcp-tls-terminate": True,
            "tcp-hostname": "example.com",
            "tcp-retry-count": 3,
            "tcp-retry-redispatch": True,
            "tcp-load-balancing-algorithm": "source",
            "tcp-load-balancing-consistent-hashing": True,
        },
        relations=[ops.testing.Relation("haproxy-route-tcp")],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), in_)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    application_data: dict = dict(out.get_relations("haproxy-route-tcp")[0].local_app_data)
    assert application_data["port"] == "4000"
    assert application_data["backend_port"] == "5000"
    assert application_data["hosts"] == '["10.0.0.1"]'
    assert application_data["sni"] == '"example.com"'
    assert json.loads(application_data["retry"]) == {"count": 3, "redispatch": True}
    assert json.loads(application_data["load_balancing"]) == {
        "algorithm": "source",
        "consistent_hashing": True,
    }


def test_haproxy_route_tcp_blocked_with_ingress(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: haproxy-route-tcp relation exists with an ingress relation.
    act: trigger config-changed.
    assert: status is Blocked with a message that haproxy-route-tcp cannot be used with ingress.
    """
    state = ops.testing.State(
        config={
            "tcp-backend-addresses": "10.0.0.1",
            "tcp-frontend-port": 4000,
            "tcp-backend-port": 5000,
        },
        relations=[
            ops.testing.Relation("haproxy-route-tcp"),
            ops.testing.Relation("ingress"),
        ],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert (
        out.unit_status.message
        == "haproxy-route-tcp cannot be used with ingress relation. Use integrator mode only."
    )


@pytest.mark.parametrize(
    ("relation1", "relation2"),
    [
        pytest.param(r1, r2, id=f"{r1} and {r2}")
        for r1, r2 in combinations(["haproxy-route", "haproxy-route-tcp"], 2)
    ],
)
def test_routes_mutual_exclusivity(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    relation1: str,
    relation2: str,
):
    """
    arrange: both multiple relations are present.
    act: trigger config-changed.
    assert: status is Blocked about only one route type supported.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation(relation1),
            ops.testing.Relation(relation2),
        ],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert (
        out.unit_status.message
        == "Only one route relation type should exist (haproxy-route or haproxy-route-tcp)."
    )
