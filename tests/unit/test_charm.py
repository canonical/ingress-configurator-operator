# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress configurator charm."""

import json
from itertools import combinations
from typing import TYPE_CHECKING
from unittest.mock import ANY

import ops.testing
import pytest

if TYPE_CHECKING:
    from charm import IngressConfiguratorCharm


def test_config_changed_invalid_state(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare some state with invalid backend-addresses.
    act: trigger a config changed event.
    assert: status is blocked.
    """
    charm_state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1,invalid", "backend-ports": "8080"},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), charm_state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)


def test_config_changed_ingress_relation_not_ready(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare state with haproxy-route and an ingress relation whose requirer
        hasn't populated the databag yet (empty remote app data).
    act: trigger a config-changed event.
    assert: the unit is waiting, not blocked or erroring.
    """
    charm_state = ops.testing.State(
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation("ingress"),
        ],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.WaitingStatus("Waiting for ingress relation data.")


@pytest.mark.parametrize(
    "context_fixture",
    [
        pytest.param("context_machine", id="machine"),
        pytest.param("context_k8s", id="k8s"),
    ],
)
def test_config_changed_adapter_with_backend_addresses_conflict(
    context_fixture: str,
    request: pytest.FixtureRequest,
):
    """
    arrange: ingress relation is ready (adapter mode trigger) and backend-addresses config is
        also set (integrator mode trigger). Applies to both machine and Kubernetes substrates.
    act: trigger config-changed.
    assert: status is Blocked — no valid mode can be determined.
    """
    context = request.getfixturevalue(context_fixture)
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "ingress",
                remote_app_data={
                    "model": '"test-model"',
                    "name": '"some-app"',
                    "port": "8080",
                },
                remote_units_data={0: {"host": '"host.example"', "ip": '"10.1.0.1"'}},
            ),
        ],
        leader=True,
    )

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Remove backend config or the ingress relation - only one can be used at a time."
    )


def test_config_changed_no_valid_mode(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: haproxy-route relation exists but neither an ingress relation nor backend-addresses
        and backend-ports config are present (machine substrate).
    act: trigger config-changed.
    assert: status is Blocked — no valid mode can be determined.
    """
    state = ops.testing.State(
        config={},
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Ingress relation or backend config required."
    )


@pytest.mark.usefixtures("mock_lightkube")
def test_config_changed_kubernetes_without_ingress_relation(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: prepare state with haproxy-route but no ingress relation on a Kubernetes substrate.
    act: trigger a config-changed event.
    assert: the unit is blocked because adapter mode requires an ingress relation on Kubernetes.
    """
    charm_state = ops.testing.State(
        relations=[ops.testing.Relation("haproxy-route")],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), charm_state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "Ingress relation required on Kubernetes substrate."
    )


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
    assert application_data["port_mapping"] == '"4000:5000"'
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
        for r1, r2 in combinations(["haproxy-route", "haproxy-route-tcp", "gateway-route"], 2)
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
        == "Only one route relation type should exist (haproxy-route, haproxy-route-tcp, or gateway-route)."
    )


@pytest.mark.parametrize(
    ("context_fixture", "unsupported_relation", "expected_message"),
    [
        pytest.param(
            "context_machine",
            "haproxy-route-tcp",
            "cache-config is not supported for the haproxy-route-tcp relation",
            id="haproxy-route-tcp",
        ),
        pytest.param(
            "context_k8s",
            "gateway-route",
            "cache-config is not supported for the gateway-route relation",
            id="gateway-route",
        ),
    ],
)
def test_cache_config_unsupported_for_route(
    context_fixture: str,
    unsupported_relation: str,
    expected_message: str,
    request: pytest.FixtureRequest,
):
    """
    arrange: cache-config and an unsupported route relation are both present.
    act: trigger config-changed.
    assert: BlockedStatus explaining that cache-config does not support that route.
    """
    context = request.getfixturevalue(context_fixture)
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation(unsupported_relation),
            ops.testing.Relation("cache-config"),
        ],
        leader=True,
    )
    out = context.run(context.on.config_changed(), state)
    assert out.unit_status == ops.testing.BlockedStatus(expected_message)


@pytest.mark.parametrize(
    "cache_backend",
    [
        pytest.param(None, id="missing"),
        pytest.param("not-a-url", id="malformed URL"),
        pytest.param("http://cache.example.com:9000", id="DNS name"),
        pytest.param("http://10.1.0.5:0", id="invalid port"),
    ],
)
def test_cache_config_without_usable_backend_keeps_relation_unpublished(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    cache_backend: str | None,
):
    """
    arrange: cache-config has no usable cache-backend, because it is missing or invalid.
    act: trigger config-changed.
    assert: reconciliation remains active without publishing HAProxy cache data.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={
                    0: {} if cache_backend is None else {"cache-backend": cache_backend}
                },
            ),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)
    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    assert out.get_relations("haproxy-route")[0].local_app_data == {}


def test_cache_config_invalid_fail_timeout_is_blocked(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: cache-config relation present with an invalid cache-fail-timeout value.
    act: trigger config-changed.
    assert: BlockedStatus — invalid cache-config configuration.
    """
    state = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "8080",
            "cache-fail-timeout": "not-a-time",
        },
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation("cache-config"),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)
    assert out.unit_status == ops.testing.BlockedStatus("Invalid cache-config configuration")


def test_cache_config_replaces_backends_when_available(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: cache-config relation present, content-cache has written an http:// cache-backend.
    act: trigger config-changed.
    assert: ActiveStatus, backends replaced with content-cache address, protocol set to http.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={0: {"cache-backend": "http://10.1.0.5:9000"}},
            ),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    assert haproxy_data["hosts"] == '["10.1.0.5"]'
    assert haproxy_data["ports"] == "[9000]"
    # Library omits protocol from the databag when it is the default ("http").
    assert "protocol" not in haproxy_data


def test_cache_config_https_cache_backend_with_hostname(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: content-cache has a TLS frontend and publishes an https:// cache-backend;
             hostname is configured on ingress-configurator.
    act: trigger config-changed.
    assert: ActiveStatus, protocol set to https so haproxy connects to content-cache via TLS.
    """
    state = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "8080",
            "hostname": "myapp.example.com",
        },
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={0: {"cache-backend": "https://10.1.0.5:9443"}},
            ),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    assert haproxy_data["hosts"] == '["10.1.0.5"]'
    assert haproxy_data["ports"] == "[9443]"
    assert haproxy_data["protocol"] == '"https"'


def test_cache_config_sends_relation_data_to_content_cache(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: cache-config relation present with content-cache backends available.
    act: trigger config-changed.
    assert: ingress-configurator wrote backends to the cache-config app databag.
    """
    state = ops.testing.State(
        config={
            "backend-addresses": "10.0.0.1",
            "backend-ports": "8080",
            "cache-proxy-cache-valid": "200 1h",
        },
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={0: {"cache-backend": "http://10.1.0.5:9000"}},
            ),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    cache_config_rel = out.get_relations("cache-config")[0]
    local_app_data: dict = dict(cache_config_rel.local_app_data)
    assert json.loads(local_app_data["backends"]) == ["http://10.0.0.1:8080"]
    assert "backend_hostname" not in local_app_data
    assert local_app_data["healthcheck_ssl_verify"] == "true"
    assert json.loads(local_app_data["proxy_cache_valid"]) == ["200 1h"]


def test_cache_config_derives_hosts_and_ports_from_every_cache_backend(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: cache-config with two content-cache units, each on a different port.
    act: trigger config-changed.
    assert: every cache-backend URL contributes its host and its port, with no address
            or port dropped and none invented.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={
                    0: {"cache-backend": "http://10.1.0.5:9000"},
                    1: {"cache-backend": "http://10.1.0.6:9001"},
                },
            ),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    # hosts and ports are published as two independent lists, which haproxy then
    # cross-products into four server entries, two of them fictional. That is
    # pre-existing behaviour and is not what this test pins: it pins only that both
    # cache-backends are represented and that neither list gains or loses an entry.
    assert sorted(json.loads(haproxy_data["hosts"])) == ["10.1.0.5", "10.1.0.6"]
    assert sorted(json.loads(haproxy_data["ports"])) == [9000, 9001]


def test_cache_config_removed_reverts_to_original_backends(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: no cache-config relation (simulates relation-broken completing).
    act: trigger config-changed.
    assert: ActiveStatus and haproxy-route uses the original backend address.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
        ],
        leader=True,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    assert haproxy_data["hosts"] == '["10.0.0.1"]'
    assert haproxy_data["ports"] == "[8080]"


def test_cache_config_non_leader_does_not_write_app_databag(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: cache-config relation present with cache-backend available, leader=False.
    act: trigger config-changed.
    assert: charm does not crash; cache-config app databag is not written by non-leader.
    """
    state = ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080"},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={0: {"cache-backend": "http://10.1.0.5:9000"}},
            ),
        ],
        leader=False,
    )
    out = context_machine.run(context_machine.on.config_changed(), state)

    # Non-leader still gets WaitingStatus (it read the cache-backend, but haproxy-route
    # app databag is also leader-only — non-leader reaches ActiveStatus only if the
    # haproxy-route write is also guarded; here we assert it does not crash).
    cache_rel = out.get_relations("cache-config")[0]
    assert dict(cache_rel.local_app_data) == {}, "non-leader must not write app databag"


def _cache_backend_state(
    cache_backend: str,
    config: dict[str, str | int | float | bool] | None = None,
    leader: bool = True,
) -> ops.testing.State:
    """Build a state with haproxy-route and a content-cache unit publishing cache_backend.

    Args:
        cache_backend: The URL the content-cache unit publishes.
        config: Extra charm config entries merged over the integrator-mode defaults.
        leader: Whether this unit is the Juju leader.

    Returns:
        The ops.testing.State to run against.
    """
    return ops.testing.State(
        config={"backend-addresses": "10.0.0.1", "backend-ports": "8080", **(config or {})},
        relations=[
            ops.testing.Relation("haproxy-route"),
            ops.testing.Relation(
                "cache-config",
                remote_units_data={0: {"cache-backend": cache_backend}},
            ),
        ],
        leader=leader,
    )


@pytest.mark.parametrize(
    "cache_backend, expected_port",
    [
        pytest.param("http://[fd00::5]:9000", 9000, id="ipv6 with port"),
        pytest.param("http://[fd00::5]", 80, id="ipv6 without port"),
    ],
)
def test_cache_config_ipv6_cache_backend_is_unbracketed(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
    cache_backend: str,
    expected_port: int,
):
    """
    arrange: content-cache publishes an IPv6 cache-backend, with and without a port.
    act: trigger config-changed.
    assert: ActiveStatus and the address reaches haproxy-route unbracketed, since
            HaproxyRouteState.backend_addresses only accepts the bare IPvAnyAddress form.
    """
    out = context_machine.run(
        context_machine.on.config_changed(), _cache_backend_state(cache_backend)
    )

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    assert json.loads(haproxy_data["hosts"]) == ["fd00::5"]
    assert json.loads(haproxy_data["ports"]) == [expected_port]


def test_cache_config_wildcard_hostname_with_http_origin_is_active(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: a wildcard hostname, which haproxy-route accepts, with an http origin.
    act: trigger config-changed.
    assert: ActiveStatus and no backend_hostname in the databag. backend_hostname is only
            for origin TLS verification, so sending a wildcard content-cache would reject
            for a plaintext origin would block on a value that is never used.
    """
    out = context_machine.run(
        context_machine.on.config_changed(),
        _cache_backend_state("http://10.1.0.5:9000", {"hostname": "*.example.com"}),
    )

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    cache_data: dict = dict(out.get_relations("cache-config")[0].local_app_data)
    assert "backend_hostname" not in cache_data


def test_cache_config_https_cache_backend_without_port_uses_443(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: content-cache publishes an https cache-backend with no explicit port.
    act: trigger config-changed.
    assert: ActiveStatus with port 443 and the https protocol, covering the portless
            path for https as the IPv6 cases cover it for http.
    """
    out = context_machine.run(
        context_machine.on.config_changed(),
        _cache_backend_state("https://10.1.0.5", {"hostname": "myapp.example.com"}),
    )

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    haproxy_data: dict = dict(out.get_relations("haproxy-route")[0].local_app_data)
    assert json.loads(haproxy_data["hosts"]) == ["10.1.0.5"]
    assert json.loads(haproxy_data["ports"]) == [443]
    assert haproxy_data["protocol"] == '"https"'


def test_cache_config_https_origin_sends_backend_hostname(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: an https origin with a non-wildcard hostname.
    act: trigger config-changed.
    assert: the databag carries backend_hostname, since content-cache needs it as
            proxy_ssl_name to verify the origin's certificate. This is the counterpart
            to the http case, where the key is deliberately omitted.
    """
    out = context_machine.run(
        context_machine.on.config_changed(),
        _cache_backend_state(
            "http://10.1.0.5:9000",
            {"hostname": "myapp.example.com", "backend-protocol": "https"},
        ),
    )

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    cache_data: dict = dict(out.get_relations("cache-config")[0].local_app_data)
    assert cache_data["backend_hostname"] == "myapp.example.com"
