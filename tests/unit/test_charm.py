# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

from unittest.mock import ANY, MagicMock

import ops.testing
import pytest

import state
from charm import IngressConfiguratorCharm


def test_config_changed_no_haproxy_route_relation(context):
    """
    arrange: prepare some valid state without haproxy-route relation.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": ",127.0.0.1,127.0.0.2", "backend-ports": "8080,8081"},
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus("Missing haproxy-route relation.")


def test_config_changed_invalid_state(monkeypatch: pytest.MonkeyPatch, context):
    """
    arrange: prepare some state with invalid backend-addresses.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    monkeypatch.setattr(state.State, "from_charm", MagicMock(side_effect=state.InvalidStateError))
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus()


def test_config_changed_integrator(context):
    """
    arrange: prepare some valid state for an integrator.
    act: trigger a config changed event.
    assert: status is active.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,10.0.0.2", "backend-ports": "8080,8081"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context.run(context.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.ActiveStatus()


def test_protocol_propagated_to_haproxy(context: ops.testing.Context):
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
    out = context.run(context.on.config_changed(), in_)

    assert out.unit_status == ops.testing.ActiveStatus("")
    assert out.get_relations("haproxy-route")[0].local_app_data == {
        "service": ANY,
        "ports": "[80]",
        "hosts": '["10.0.0.1"]',
        "protocol": '"https"',
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
        context: ops.testing.Context[IngressConfiguratorCharm],
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
        context.run(context.on.action("get-proxied-endpoints"), charm_state)

        out = context.action_results

        assert out == {"endpoints": endpoints}, "Unexpected action results."

    def test_no_endpoints(
        self,
        context: ops.testing.Context[IngressConfiguratorCharm],
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
        context.run(context.on.action("get-proxied-endpoints"), charm_state)

        out = context.action_results

        assert out == {}, "Unexpected action results."

    def test_no_haproxy_route_relation(
        self,
        context: ops.testing.Context[IngressConfiguratorCharm],
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
        context.run(context.on.action("get-proxied-endpoints"), charm_state)

        out = context.action_results
        assert out == {}
