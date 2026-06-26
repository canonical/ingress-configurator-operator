# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the headless backend helpers in http_route."""

from unittest.mock import MagicMock

import pytest
from lightkube import ApiError

from http_route import (
    MANAGED_BY_LABEL,
    delete_backend_services_owned_by,
    ensure_workload_backend_service,
)
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


def test_delete_backend_services_owned_by_deletes_matching_resources():
    """
    arrange: mock a client listing one matching EndpointSlice and one matching Service
    act: call delete_backend_services_owned_by
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

    delete_backend_services_owned_by(client, "testing-model", "my-charm")

    client.delete.assert_any_call(EndpointSlice, name="my-app-headless", namespace="testing-model")
    client.delete.assert_any_call(Service, name="my-app-headless", namespace="testing-model")


def test_delete_backend_services_owned_by_skips_other_charms():
    """
    arrange: mock a client that returns empty lists (K8s filters by label selector server-side)
    act: call delete_backend_services_owned_by with "my-charm"
    assert: list is called with MANAGED_BY_LABEL="my-charm" so other charms' resources are
        never returned, and no deletes happen
    """
    client = MagicMock()
    client.list.return_value = []

    delete_backend_services_owned_by(client, "testing-model", "my-charm")

    for call in client.list.call_args_list:
        assert call.kwargs.get("labels", {}).get(MANAGED_BY_LABEL) == "my-charm"
    client.delete.assert_not_called()


def test_delete_backend_services_owned_by_no_resources():
    """
    arrange: mock a client listing no resources
    act: call delete_backend_services_owned_by
    assert: no deletes are performed
    """
    client = MagicMock()
    client.list.return_value = []

    delete_backend_services_owned_by(client, "testing-model", "my-charm")

    client.delete.assert_not_called()


def test_delete_backend_services_owned_by_raises_on_403():
    """
    arrange: client raises ApiError 403 on list
    act: call delete_backend_services_owned_by
    assert: InvalidKubernetesPermissionError is raised
    """
    client = MagicMock()
    client.list.side_effect = _make_api_error(403)

    with pytest.raises(InvalidKubernetesPermissionError, match="--trust"):
        delete_backend_services_owned_by(client, "testing-model", "my-charm")


def test_delete_backend_services_owned_by_reraises_other_api_errors():
    """
    arrange: client raises ApiError 500 on list
    act: call delete_backend_services_owned_by
    assert: the ApiError is re-raised
    """
    client = MagicMock()
    client.list.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        delete_backend_services_owned_by(client, "testing-model", "my-charm")


def test_delete_backend_services_owned_by_skips_excluded_names():
    """
    arrange: mock a client listing one EndpointSlice and two Services, one of
        which is in the exclude set.
    act: call delete_backend_services_owned_by with exclude={"keep-svc"}
    assert: only the non-excluded Service is deleted; the EndpointSlice is deleted
        (no name match in exclude); the excluded Service is never deleted.
    """
    from lightkube.resources.core_v1 import Service
    from lightkube.resources.discovery_v1 import EndpointSlice

    client = MagicMock()
    es = _make_endpoint_slice("my-app-headless")
    keep_svc = _make_service("keep-svc")
    delete_svc = _make_service("old-svc")

    def list_side_effect(resource_type: type, **_: object) -> list:
        if resource_type is EndpointSlice:
            return [es]
        if resource_type is Service:
            return [keep_svc, delete_svc]
        return []

    client.list.side_effect = list_side_effect

    delete_backend_services_owned_by(client, "testing-model", "my-charm", exclude={"keep-svc"})

    client.delete.assert_any_call(EndpointSlice, name="my-app-headless", namespace="testing-model")
    client.delete.assert_any_call(Service, name="old-svc", namespace="testing-model")
    for call in client.delete.call_args_list:
        assert call.kwargs.get("name") != "keep-svc"


# ---------------------------------------------------------------------------
# ensure_workload_backend_service tests
# ---------------------------------------------------------------------------


def test_ensure_workload_backend_service_creates_correct_service():
    """
    arrange: mock a lightkube client
    act: call ensure_workload_backend_service for target app "my-app", port 8080
    assert: client.apply is called once with a Service that has
        selector={"app.kubernetes.io/name": "my-app"}, port/targetPort=8080,
        and MANAGED_BY_LABEL set to the owner charm name.
    """
    from lightkube.resources.core_v1 import Service

    client = MagicMock()

    ensure_workload_backend_service(
        client,
        "testing-model",
        "ingress-configurator-my-app",
        "my-app",
        8080,
        "ingress-configurator",
    )

    assert client.apply.call_count == 1
    svc = client.apply.call_args.args[0]
    assert isinstance(svc, Service)
    assert svc.metadata is not None
    assert svc.metadata.name == "ingress-configurator-my-app"
    assert svc.metadata.namespace == "testing-model"
    assert svc.metadata.labels is not None
    assert svc.metadata.labels.get(MANAGED_BY_LABEL) == "ingress-configurator"
    assert svc.spec is not None
    assert svc.spec.selector == {"app.kubernetes.io/name": "my-app"}
    assert svc.spec.ports is not None
    assert svc.spec.ports[0].port == 8080
    assert svc.spec.ports[0].targetPort == 8080


def test_ensure_workload_backend_service_raises_on_403():
    """
    arrange: client raises ApiError 403 on apply
    act: call ensure_workload_backend_service
    assert: InvalidKubernetesPermissionError is raised
    """
    client = MagicMock()
    client.apply.side_effect = _make_api_error(403)

    with pytest.raises(InvalidKubernetesPermissionError, match="--trust"):
        ensure_workload_backend_service(
            client, "testing-model", "charm-my-app", "my-app", 8080, "charm"
        )


def test_ensure_workload_backend_service_reraises_other_api_errors():
    """
    arrange: client raises ApiError 500 on apply
    act: call ensure_workload_backend_service
    assert: the ApiError is re-raised
    """
    client = MagicMock()
    client.apply.side_effect = _make_api_error(500)

    with pytest.raises(ApiError):
        ensure_workload_backend_service(
            client, "testing-model", "charm-my-app", "my-app", 8080, "charm"
        )
