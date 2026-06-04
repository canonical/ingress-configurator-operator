# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for HaproxyRouteState in adapter mode (for_adapter_mode)."""

from unittest.mock import Mock

from charms.traefik_k8s.v2.ingress import (
    IngressRequirerAppData,
    IngressRequirerData,
    IngressRequirerUnitData,
)
from ops import CharmBase

from state.haproxy_route import BackendState, HaproxyRouteState


def _make_adapter_state(charm, ingress_data):
    """Build HaproxyRouteState via the two-step BackendState + from_charm API."""
    service = f"{charm.model.name}-{charm.app.name}"
    backend_state = BackendState.for_adapter_mode(charm, ingress_data)
    return HaproxyRouteState.from_charm(charm, backend_state, service)


def test_adapter_state_from_charm():
    """
    arrange: mock a charm with an ingress relation
    act: instantiate a State via for_adapter_mode
    assert: the data matches the charm configuration
    """
    charm = Mock(CharmBase)
    charm.config = {
        "health-check-interval": 20,
        "health-check-rise": 3,
        "health-check-fall": 4,
        "health-check-path": "/health",
        "health-check-port": 8080,
        "retry-count": 1,
        "retry-redispatch": True,
        "timeout-server": 11,
        "timeout-connect": 12,
        "timeout-queue": 13,
        "paths": "/api/v1,/api/v2",
        "hostname": "api.example.com",
        "additional-hostnames": "api2.example.com,api3.example.com",
        "http-server-close": True,
        "allow-http": True,
    }
    ingress_relation_data = IngressRequirerData(
        app=IngressRequirerAppData(model="model", name="name", port=8080),
        units=[IngressRequirerUnitData(host="sample.host", ip="127.0.0.1")],
    )
    charm_state = _make_adapter_state(charm, ingress_relation_data)

    assert [str(address) for address in charm_state.backend_addresses] == [
        ingress_relation_data.units[0].ip
    ]
    assert charm_state.backend_ports == [ingress_relation_data.app.port]
    assert charm_state.backend_protocol == "http"
    assert charm_state.health_check.interval == charm.config.get("health-check-interval")
    assert charm_state.health_check.rise == charm.config.get("health-check-rise")
    assert charm_state.health_check.fall == charm.config.get("health-check-fall")
    assert charm_state.health_check.path == charm.config.get("health-check-path")
    assert charm_state.health_check.port == charm.config.get("health-check-port")
    assert charm_state.retry.count == charm.config.get("retry-count")
    assert charm_state.retry.redispatch == charm.config.get("retry-redispatch")
    assert charm_state.timeout.server == charm.config.get("timeout-server")
    assert charm_state.timeout.connect == charm.config.get("timeout-connect")
    assert charm_state.timeout.queue == charm.config.get("timeout-queue")
    assert charm_state.paths == charm.config.get("paths").split(",")
    assert charm_state.hostname == charm.config.get("hostname")
    assert charm_state.additional_hostnames == charm.config.get("additional-hostnames").split(",")
    assert charm_state.http_server_close == charm.config.get("http-server-close")
    assert charm_state.allow_http == charm.config.get("allow-http")
