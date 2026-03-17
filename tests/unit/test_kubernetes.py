# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the kubernetes module."""

from unittest.mock import MagicMock

from kubernetes import KubernetesData, create_nodeport_service, delete_nodeport_service, ensure_nodeport_service, get_kubernetes_data, get_node_ips, get_nodeport_service, replace_nodeport_service


def _make_node(*addresses: tuple[str, str]) -> MagicMock:
    """Create a mock Node with the given (type, address) pairs."""
    node = MagicMock()
    node.status.addresses = [
        MagicMock(type=addr_type, address=addr) for addr_type, addr in addresses
    ]
    return node


def test_get_node_ips_returns_internal_ips():
    """
    arrange: mock a client returning two nodes each with an InternalIP
    act: call get_node_ips
    assert: the InternalIP addresses of all nodes are returned
    """
    client = MagicMock()
    client.list.return_value = [
        _make_node(("InternalIP", "10.0.0.1"), ("Hostname", "node1")),
        _make_node(("InternalIP", "10.0.0.2"), ("ExternalIP", "1.2.3.4")),
    ]

    ips = get_node_ips(client)

    assert ips == ["10.0.0.1", "10.0.0.2"]


def test_get_node_ips_skips_non_internal_addresses():
    """
    arrange: mock a client returning a node with only ExternalIP and Hostname
    act: call get_node_ips
    assert: an empty list is returned
    """
    client = MagicMock()
    client.list.return_value = [
        _make_node(("ExternalIP", "1.2.3.4"), ("Hostname", "node1")),
    ]

    ips = get_node_ips(client)

    assert ips == []


def test_get_node_ips_empty_cluster():
    """
    arrange: mock a client returning no nodes
    act: call get_node_ips
    assert: an empty list is returned
    """
    client = MagicMock()
    client.list.return_value = []

    ips = get_node_ips(client)

    assert ips == []


def test_create_nodeport_service():
    """
    arrange: mock a lightkube client
    act: call create_nodeport_service with port 9090, protocol UDP, and app_name "myapp"
    assert: the created service has the correct name, type, selector, port and protocol
    """
    client = MagicMock()

    create_nodeport_service(client, port=9090, protocol="UDP", app_name="myapp")

    service = client.create.call_args[0][0]
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
    assert: a KubernetesData instance is returned with the service and node details
    """
    client = MagicMock()
    mock_service = MagicMock()
    mock_service.metadata.name = "myapp-service"
    mock_service.spec.ports = [MagicMock(targetPort=8080, protocol="TCP")]
    client.get.return_value = mock_service
    client.list.return_value = [_make_node(("InternalIP", "10.0.0.1"))]

    result = get_kubernetes_data(client, "myapp")

    assert isinstance(result, KubernetesData)
    assert result.service_name == "myapp-service"
    assert result.service_target_port == 8080
    assert result.service_protocol == "TCP"
    assert result.node_ips == ["10.0.0.1"]


def test_kubernetes_data_holds_node_ips_and_service_details():
    """
    arrange: create a KubernetesData with known values
    act: access all fields
    assert: all fields match the provided values
    """
    data = KubernetesData(
        node_ips=["10.0.0.1", "10.0.0.2"],
        service_name="myapp-service",
        service_target_port=8080,
        service_protocol="TCP",
    )

    assert data.node_ips == ["10.0.0.1", "10.0.0.2"]
    assert data.service_name == "myapp-service"
    assert data.service_target_port == 8080
    assert data.service_protocol == "TCP"


def _make_api_error(code: int) -> "ApiError":
    """Create an ApiError with the given HTTP status code."""
    from lightkube import ApiError

    return ApiError(status={"code": code, "message": str(code), "status": "Failure"})


# replace_nodeport_service


def test_replace_nodeport_service_name():
    """
    arrange: mock a lightkube client
    act: call replace_nodeport_service with app_name "myapp"
    assert: the service is replaced with name "myapp-service"
    """
    client = MagicMock()

    replace_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.replace.call_args[0][0]
    assert service.metadata.name == "myapp-service"


def test_replace_nodeport_service_type():
    """
    arrange: mock a lightkube client
    act: call replace_nodeport_service
    assert: the replaced service spec type is NodePort
    """
    client = MagicMock()

    replace_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.replace.call_args[0][0]
    assert service.spec.type == "NodePort"


def test_replace_nodeport_service_selector():
    """
    arrange: mock a lightkube client
    act: call replace_nodeport_service with app_name "myapp"
    assert: the selector targets the given app name
    """
    client = MagicMock()

    replace_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.replace.call_args[0][0]
    assert service.spec.selector == {"app": "myapp"}


def test_replace_nodeport_service_port_and_protocol():
    """
    arrange: mock a lightkube client
    act: call replace_nodeport_service with port 9090 and protocol UDP
    assert: the replaced service port and protocol match the supplied values
    """
    client = MagicMock()

    replace_nodeport_service(client, port=9090, protocol="UDP", app_name="backend")

    service = client.replace.call_args[0][0]
    assert service.spec.ports[0].port == 9090
    assert service.spec.ports[0].protocol == "UDP"


# delete_nodeport_service


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


# ensure_nodeport_service


def test_ensure_nodeport_service_creates_when_not_found():
    """
    arrange: mock a client that raises ApiError 404 on get
    act: call ensure_nodeport_service
    assert: create_nodeport_service is called with the correct arguments
    """
    client = MagicMock()
    client.get.side_effect = _make_api_error(404)

    ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    assert client.create.called
    service = client.create.call_args[0][0]
    assert service.metadata.name == "myapp-service"
    assert service.spec.ports[0].port == 8080
    assert service.spec.ports[0].protocol == "TCP"


def test_ensure_nodeport_service_does_nothing_when_port_and_protocol_match():
    """
    arrange: mock a client returning a service whose port and protocol already match
    act: call ensure_nodeport_service
    assert: neither create nor replace is called
    """
    client = MagicMock()
    existing = MagicMock()
    existing.spec.ports = [MagicMock(port=8080, protocol="TCP")]
    client.get.return_value = existing

    ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    client.create.assert_not_called()
    client.replace.assert_not_called()


def test_ensure_nodeport_service_replaces_when_port_differs():
    """
    arrange: mock a client returning a service with a different port
    act: call ensure_nodeport_service with the new port
    assert: replace_nodeport_service is called with the new port
    """
    client = MagicMock()
    existing = MagicMock()
    existing.spec.ports = [MagicMock(port=9090, protocol="TCP")]
    client.get.return_value = existing

    ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    assert client.replace.called
    service = client.replace.call_args[0][0]
    assert service.spec.ports[0].port == 8080


def test_ensure_nodeport_service_replaces_when_protocol_differs():
    """
    arrange: mock a client returning a service with a different protocol
    act: call ensure_nodeport_service with the new protocol
    assert: replace_nodeport_service is called with the new protocol
    """
    client = MagicMock()
    existing = MagicMock()
    existing.spec.ports = [MagicMock(port=8080, protocol="UDP")]
    client.get.return_value = existing

    ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    assert client.replace.called
    service = client.replace.call_args[0][0]
    assert service.spec.ports[0].protocol == "TCP"


def test_ensure_nodeport_service_reraises_non_404_api_error():
    """
    arrange: mock a client that raises ApiError 500 on get
    act: call ensure_nodeport_service
    assert: the ApiError is re-raised
    """
    from lightkube import ApiError

    import pytest

    client = MagicMock()
    client.get.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        ensure_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")
