# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the headless backend helpers in http_route."""

from unittest.mock import MagicMock

import pytest
from lightkube import ApiError

from http_route import MANAGED_BY_LABEL, apply_headless_backend, delete_headless_backends_owned_by
from kubernetes import InvalidKubernetesPermissionError


def _make_api_error(code: int) -> ApiError:
    """Create an ApiError with the given HTTP status code."""
    return ApiError(status={"code": code, "message": str(code), "status": "Failure"})


def _make_service(name: str) -> MagicMock:
    """Create a mock Service with the given name."""
    svc = MagicMock()
    svc.metadata.name = name
    return svc


def _make_endpoint_slice(name: str) -> MagicMock:
    """Create a mock EndpointSlice with the given name."""
    es = MagicMock()
    es.metadata.name = name
    return es


def test_apply_headless_backend_creates_correct_resources():
    """
    arrange: mock a lightkube client
    act: call apply_headless_backend with name "my-app-headless", IPv4 addresses,
        port 8080, charm_name "my-charm", and address_type "IPv4"
    assert: client.apply is called twice — first with a headless Service (clusterIP=None,
        correct labels/annotations/port), then with an EndpointSlice (addressType=IPv4,
        correct endpoints, service-name label, owning-charm annotation)
    """
    from lightkube.resources.core_v1 import Service
    from lightkube.resources.discovery_v1 import EndpointSlice

    client = MagicMock()

    apply_headless_backend(
        client,
        "testing-model",
        "my-app-headless",
        ["10.0.0.1", "10.0.0.2"],
        8080,
        "my-charm",
        "IPv4",
    )

    assert client.apply.call_count == 2
    svc = next(c.args[0] for c in client.apply.call_args_list if isinstance(c.args[0], Service))
    es = next(
        c.args[0] for c in client.apply.call_args_list if isinstance(c.args[0], EndpointSlice)
    )

    assert svc.metadata is not None
    assert svc.metadata.name == "my-app-headless"
    assert svc.metadata.labels is not None
    assert svc.metadata.labels.get(MANAGED_BY_LABEL) == "my-charm"
    assert svc.spec is not None
    assert svc.spec.clusterIP == "None"
    assert svc.spec.ports is not None
    assert svc.spec.ports[0].port == 8080

    assert es.addressType == "IPv4"
    assert len(es.endpoints) == 2
    assert es.endpoints[0].addresses == ["10.0.0.1"]
    assert es.endpoints[1].addresses == ["10.0.0.2"]
    assert es.ports is not None
    assert es.ports[0].port == 8080
    assert es.metadata is not None
    assert es.metadata.labels is not None
    assert es.metadata.labels.get("kubernetes.io/service-name") == "my-app-headless"
    assert es.metadata.labels.get(MANAGED_BY_LABEL) == "my-charm"


def test_apply_headless_backend_raises_on_service_403():
    """
    arrange: client raises ApiError 403 when applying the Service
    act: call apply_headless_backend
    assert: InvalidKubernetesPermissionError is raised; EndpointSlice is never applied
    """
    client = MagicMock()
    client.apply.side_effect = _make_api_error(403)

    with pytest.raises(InvalidKubernetesPermissionError, match="--trust"):
        apply_headless_backend(
            client, "testing-model", "my-app-headless", ["10.0.0.1"], 8080, "my-charm", "IPv4"
        )

    assert client.apply.call_count == 1


def test_apply_headless_backend_raises_on_endpoint_slice_403():
    """
    arrange: Service apply succeeds but EndpointSlice apply raises ApiError 403
    act: call apply_headless_backend
    assert: InvalidKubernetesPermissionError is raised
    """
    from lightkube.resources.core_v1 import Service

    client = MagicMock()

    def apply_side_effect(resource: object, **_: object) -> MagicMock:
        if isinstance(resource, Service):
            return MagicMock()
        raise _make_api_error(403)

    client.apply.side_effect = apply_side_effect

    with pytest.raises(InvalidKubernetesPermissionError, match="--trust"):
        apply_headless_backend(
            client, "testing-model", "my-app-headless", ["10.0.0.1"], 8080, "my-charm", "IPv4"
        )


def test_apply_headless_backend_reraises_other_api_errors():
    """
    arrange: client raises ApiError 500 on apply
    act: call apply_headless_backend
    assert: the ApiError is re-raised
    """
    client = MagicMock()
    client.apply.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        apply_headless_backend(
            client, "testing-model", "my-app-headless", ["10.0.0.1"], 8080, "my-charm", "IPv4"
        )


def test_delete_headless_backends_owned_by_deletes_matching_resources():
    """
    arrange: mock a client listing one matching EndpointSlice and one matching Service
    act: call delete_headless_backends_owned_by
    assert: both the EndpointSlice and the Service are deleted
    """
    from lightkube.resources.core_v1 import Service
    from lightkube.resources.discovery_v1 import EndpointSlice

    client = MagicMock()
    matching_es = _make_endpoint_slice("my-app-headless")
    matching_svc = _make_service("my-app-headless")

    def list_side_effect(resource_type: type, **_: object) -> list:
        if resource_type is EndpointSlice:
            return [matching_es]
        if resource_type is Service:
            return [matching_svc]
        return []

    client.list.side_effect = list_side_effect

    delete_headless_backends_owned_by(client, "testing-model", "my-charm")

    client.delete.assert_any_call(EndpointSlice, name="my-app-headless", namespace="testing-model")
    client.delete.assert_any_call(Service, name="my-app-headless", namespace="testing-model")


def test_delete_headless_backends_owned_by_skips_other_charms():
    """
    arrange: mock a client that returns empty lists (K8s filters by label selector server-side)
    act: call delete_headless_backends_owned_by with "my-charm"
    assert: list is called with MANAGED_BY_LABEL="my-charm" so other charms' resources are
        never returned, and no deletes happen
    """
    client = MagicMock()
    client.list.return_value = []

    delete_headless_backends_owned_by(client, "testing-model", "my-charm")

    for call in client.list.call_args_list:
        assert call.kwargs.get("labels", {}).get(MANAGED_BY_LABEL) == "my-charm"
    client.delete.assert_not_called()


def test_delete_headless_backends_owned_by_no_resources():
    """
    arrange: mock a client listing no resources
    act: call delete_headless_backends_owned_by
    assert: no deletes are performed
    """
    client = MagicMock()
    client.list.return_value = []

    delete_headless_backends_owned_by(client, "testing-model", "my-charm")

    client.delete.assert_not_called()


def test_delete_headless_backends_owned_by_raises_on_403():
    """
    arrange: client raises ApiError 403 on list
    act: call delete_headless_backends_owned_by
    assert: InvalidKubernetesPermissionError is raised
    """
    client = MagicMock()
    client.list.side_effect = _make_api_error(403)

    with pytest.raises(InvalidKubernetesPermissionError, match="--trust"):
        delete_headless_backends_owned_by(client, "testing-model", "my-charm")


def test_delete_headless_backends_owned_by_reraises_other_api_errors():
    """
    arrange: client raises ApiError 500 on list
    act: call delete_headless_backends_owned_by
    assert: the ApiError is re-raised
    """
    client = MagicMock()
    client.list.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        delete_headless_backends_owned_by(client, "testing-model", "my-charm")
