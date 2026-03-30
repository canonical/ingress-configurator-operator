# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the kubernetes module."""

from unittest.mock import MagicMock

from lightkube import ApiError

from kubernetes import (
    ensure_nodeport_service,
    delete_nodeport_service,
    get_kubernetes_data,
    get_nodes_ips,
    get_nodeport_service,
)
from state.charm_state import NodePortState


def _make_node(*addresses: tuple[str, str]) -> MagicMock:
    """Create a mock Node with the given (type, address) pairs."""
    node = MagicMock()
    node.status.addresses = [
        MagicMock(type=addr_type, address=addr) for addr_type, addr in addresses
    ]
    return node


def test_get_nodes_ips_returns_internal_ips():
    """
    arrange: mock a client returning two worker nodes each with an InternalIP and other address types
    act: call get_nodes_ips
    assert: only the InternalIP addresses are returned
    """
    client = MagicMock()
    client.list.return_value = [
        _make_node(("InternalIP", "10.0.0.1"), ("Hostname", "node1")),
        _make_node(("InternalIP", "10.0.0.2"), ("ExternalIP", "5.6.7.8")),
    ]

    ips = get_nodes_ips(client)

    assert ips == ["10.0.0.1", "10.0.0.2"]


def test_get_nodes_ips_skips_non_internal_ip_addresses():
    """
    arrange: mock a client returning a worker node with only ExternalIP and Hostname addresses
    act: call get_nodes_ips
    assert: an empty list is returned
    """
    client = MagicMock()
    client.list.return_value = [
        _make_node(("ExternalIP", "1.2.3.4"), ("Hostname", "node1")),
    ]

    ips = get_nodes_ips(client)

    assert ips == []


def test_get_nodes_ips_empty_cluster():
    """
    arrange: mock a client returning no nodes
    act: call get_nodes_ips
    assert: an empty list is returned
    """
    client = MagicMock()
    client.list.return_value = []

    ips = get_nodes_ips(client)

    assert ips == []


def test_ensure_nodeport_service():
    """
    arrange: mock a lightkube client
    act: call ensure_nodeport_service with port 9090, protocol UDP, and app_name "myapp"
    assert: the applied service has the correct name, type, selector, port and protocol
    """
    client = MagicMock()

    ensure_nodeport_service(client, port=9090, protocol="UDP", app_name="myapp")

    service = client.apply.call_args[0][0]
    assert service.metadata.name == "myapp-service"
    assert service.spec.type == "NodePort"
    assert service.spec.selector == {"app": "myapp"}
    assert service.spec.ports[0].port == 9090
    assert service.spec.ports[0].protocol == "UDP"


def test_get_nodeport_service():
    """
    arrange: mock a lightkube client returning a service object
    act: call get_nodeport_service with app_name "myapp"
    assert: client.get is called with the service name "myapp-service" and the service is returned
    """
    from lightkube.resources.core_v1 import Service

    client = MagicMock()
    mock_service = MagicMock()
    client.get.return_value = mock_service

    result = get_nodeport_service(client, "myapp")

    client.get.assert_called_once_with(Service, name="myapp-service")
    assert result is mock_service


def test_get_kubernetes_data_returns_kubernetes_data():
    """
    arrange: mock a lightkube client returning a service object with one node
    act: call get_kubernetes_data
    assert: a NodePortState instance is returned with the service and node details
    """
    client = MagicMock()
    mock_service = MagicMock()
    mock_service.metadata.name = "myapp-service"
    mock_service.spec.ports = [MagicMock(nodePort=8080, protocol="TCP")]
    client.get.return_value = mock_service
    client.list.return_value = [_make_node(("InternalIP", "10.0.0.1"))]

    result = get_kubernetes_data(client, "myapp")

    assert isinstance(result, NodePortState)
    assert result.service_name == "myapp-service"
    assert result.backend_port == 8080
    assert result.backend_protocol == "TCP"
    assert [str(ip) for ip in result.backend_addresses] == ["10.0.0.1"]


def _make_api_error(code: int) -> ApiError:
    """Create an ApiError with the given HTTP status code."""
    return ApiError(status={"code": code, "message": str(code), "status": "Failure"})


def test_delete_nodeport_service_calls_client_delete():
    """
    arrange: mock a lightkube client
    act: call delete_nodeport_service with app_name "myapp"
    assert: client.delete is called with the service name "myapp-service"
    """
    from lightkube.resources.core_v1 import Service

    client = MagicMock()

    delete_nodeport_service(client, "myapp")

    client.delete.assert_called_once_with(Service, name="myapp-service")


def test_ensure_nodeport_service_reraises_api_error():
    """
    arrange: mock a client that raises an ApiError on apply
    act: call ensure_nodeport_service
    assert: the ApiError is re-raised
    """
    import pytest

    client = MagicMock()
    client.apply.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")
