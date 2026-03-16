# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the kubernetes module."""

from unittest.mock import MagicMock

from kubernetes import KubernetesData, create_nodeport_service, get_kubernetes_data, get_node_ips, get_nodeport_service


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


def test_create_nodeport_service_name():
    """
    arrange: mock a lightkube client
    act: call create_nodeport_service with app_name "myapp"
    assert: the service is created with name "myapp-service"
    """
    client = MagicMock()

    create_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.create.call_args[0][0]
    assert service.metadata.name == "myapp-service"


def test_create_nodeport_service_type():
    """
    arrange: mock a lightkube client
    act: call create_nodeport_service
    assert: the service spec type is NodePort
    """
    client = MagicMock()

    create_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.create.call_args[0][0]
    assert service.spec.type == "NodePort"


def test_create_nodeport_service_selector():
    """
    arrange: mock a lightkube client
    act: call create_nodeport_service with app_name "myapp"
    assert: the selector targets the given app name
    """
    client = MagicMock()

    create_nodeport_service(client, port=8080, protocol="TCP", app_name="myapp")

    service = client.create.call_args[0][0]
    assert service.spec.selector == {"app": "myapp"}


def test_create_nodeport_service_port_and_protocol():
    """
    arrange: mock a lightkube client
    act: call create_nodeport_service with port 9090 and protocol UDP
    assert: the service port and protocol match the supplied values
    """
    client = MagicMock()

    create_nodeport_service(client, port=9090, protocol="UDP", app_name="backend")

    service = client.create.call_args[0][0]
    assert service.spec.ports[0].port == 9090
    assert service.spec.ports[0].protocol == "UDP"


def test_get_nodeport_service_requests_correct_name():
    """
    arrange: mock a lightkube client
    act: call get_nodeport_service with app_name "myapp"
    assert: client.get is called with the service name "myapp-service"
    """
    from lightkube.resources.core_v1 import Service

    client = MagicMock()

    get_nodeport_service(client, "myapp")

    client.get.assert_called_once_with(Service, name="myapp-service")


def test_get_nodeport_service_returns_service():
    """
    arrange: mock a lightkube client returning a service object
    act: call get_nodeport_service
    assert: the returned value is the service from the client
    """
    client = MagicMock()
    mock_service = MagicMock()
    client.get.return_value = mock_service

    result = get_nodeport_service(client, "myapp")

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
