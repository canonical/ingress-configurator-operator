# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for HaproxyRouteState in Kubernetes adapter mode (build_for_kubernetes_adapter_mode)."""

from unittest.mock import Mock

from ops import CharmBase

from state.haproxy_route import HaproxyRouteState
from state.kubernetes import NodePortState


def _make_k8s_state(charm, kubernetes_data):
    """Build HaproxyRouteState for Kubernetes adapter mode."""
    return HaproxyRouteState.build_for_kubernetes_adapter_mode(charm, kubernetes_data)


def _make_integrator_state(charm):
    """Build HaproxyRouteState for integrator mode."""
    return HaproxyRouteState.build_for_integrator_mode(charm)


def test_state_from_charm_with_kubernetes_backend():
    """
    arrange: provide pre-resolved node IPs and a nodePort
    act: instantiate a State via build_for_kubernetes_adapter_mode
    assert: backend_addresses and backend_ports reflect the supplied values
    """
    charm = Mock(CharmBase)
    charm.config = {}

    charm_state = _make_k8s_state(
        charm,
        NodePortState(
            backend_addresses=["10.0.0.1", "10.0.0.2"],
            backend_port=8080,
            service_name="my-service",
        ),
    )

    assert [str(a) for a in charm_state.backend_addresses] == ["10.0.0.1", "10.0.0.2"]
    assert charm_state.backend_ports == [8080]
    assert charm_state.service == "my-service"


def test_state_from_charm_kubernetes_overrides_backend_addresses_and_ports():
    """
    arrange: provide node IPs and a nodePort that differ from any config values
    act: instantiate a State via build_for_kubernetes_adapter_mode
    assert: backend_addresses and backend_ports come from the supplied values, not config
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
    }

    charm_state = _make_k8s_state(
        charm,
        NodePortState(
            backend_addresses=["10.0.0.1", "10.0.0.2"],
            backend_port=8080,
            service_name="my-service",
        ),
    )

    assert [str(a) for a in charm_state.backend_addresses] == ["10.0.0.1", "10.0.0.2"]
    assert charm_state.backend_ports == [8080]


def test_state_from_charm_service_name():
    """
    arrange: mock a charm with and without pre-resolved backend data
    act: instantiate a State via build_for_kubernetes_adapter_mode and build_for_integrator_mode
    assert: service is whatever is passed to build_for_kubernetes_adapter_mode;
        for integrator mode it is "{model}-{app}"
    """
    charm = Mock(CharmBase)
    charm.model.name = "test-model"
    charm.app.name = "test-app"
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
    }

    with_kubernetes = _make_k8s_state(
        charm,
        NodePortState(
            backend_addresses=["10.0.0.1"],
            backend_port=8080,
            service_name="my-k8s-service",
        ),
    )
    without_kubernetes = _make_integrator_state(charm)

    assert with_kubernetes.service == "my-k8s-service"
    assert without_kubernetes.service == "test-model-test-app"


def test_state_from_charm_kubernetes_backend_protocol_from_config():
    """
    arrange: mock a charm with backend-protocol "https" and pre-resolved backend data
    act: instantiate a State via build_for_kubernetes_adapter_mode
    assert: backend_protocol on State reflects charm config
    """
    charm = Mock(CharmBase)
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
        "backend-protocol": "https",
    }

    charm_state = _make_k8s_state(
        charm,
        NodePortState(
            backend_addresses=["10.0.0.1"],
            backend_port=8080,
            service_name="my-service",
        ),
    )

    assert charm_state.backend_protocol == "https"


def test_state_from_charm_without_kubernetes_backend():
    """
    arrange: mock a charm with integrator config and no kubernetes data
    act: instantiate a State via build_for_integrator_mode
    assert: backend_addresses and backend_ports come from charm config
    """
    charm = Mock(CharmBase)
    charm.model.name = "test-model"
    charm.app.name = "test-app"
    charm.config = {
        "backend-addresses": "127.0.0.1",
        "backend-ports": "80",
    }

    charm_state = _make_integrator_state(charm)

    assert [str(a) for a in charm_state.backend_addresses] == ["127.0.0.1"]
    assert charm_state.backend_ports == [80]


def test_state_from_charm_kubernetes_without_config_backend():
    """
    arrange: mock a charm with no backend config and pre-resolved node IPs and nodePort
    act: instantiate a State via build_for_kubernetes_adapter_mode
    assert: State is created successfully; no config backend is required
    """
    charm = Mock(CharmBase)
    charm.model.name = "test-model"
    charm.app.name = "test-app"
    charm.config = {}

    charm_state = _make_k8s_state(
        charm,
        NodePortState(
            backend_addresses=["10.0.0.1", "10.0.0.2"],
            backend_port=30080,
            service_name="my-k8s-service",
        ),
    )

    assert [str(a) for a in charm_state.backend_addresses] == ["10.0.0.1", "10.0.0.2"]
    assert charm_state.backend_ports == [30080]
    assert charm_state.service == "my-k8s-service"
