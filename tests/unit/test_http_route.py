# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the headless backend helpers in http_route."""

from unittest.mock import MagicMock

import pytest
from lightkube import ApiError

from http_route import (
    MANAGED_BY_LABEL,
    HTTPRouteConfig,
    HTTPRouteManager,
    create_http_routes,
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


# ---------------------------------------------------------------------------
# create_http_routes tests
# ---------------------------------------------------------------------------

GW_NAME = "my-gateway"
GW_MODEL = "my-model"
BACKEND_SVC = "backend-svc"
BACKEND_PORT = 8080
APP_NAME = "my-app"
PATHS = ["/"]


def _make_http_route_manager() -> tuple[HTTPRouteManager, MagicMock]:
    """Return an HTTPRouteManager backed by a MagicMock client.

    The manager's ``apply`` method returns the resource_name argument passed to
    HTTPRouteConfig so callers can inspect what was applied.
    """
    mock_client = MagicMock()

    # apply() is called inside HTTPRouteManager.apply() — patch it so we capture
    # the config objects rather than actually calling the K8s API.
    applied: list[HTTPRouteConfig] = []

    def _fake_apply(config: HTTPRouteConfig) -> str:
        applied.append(config)
        # Return a stable resource name so delete_stale() has something to exclude.
        return f"{config.app_name}-{config.backend_service_name}-{config.scheme}"

    manager = HTTPRouteManager(
        client=mock_client,
        namespace=GW_MODEL,
        labels={MANAGED_BY_LABEL: APP_NAME},
    )
    manager.apply = _fake_apply  # type: ignore[method-assign]
    manager.delete_stale = MagicMock()  # type: ignore[method-assign]
    # Expose applied list through the mock for assertions
    mock_client._applied = applied
    return manager, mock_client


def test_create_http_routes_http_only():
    """
    arrange: https_mode=disabled, two hostnames.
    act: call create_http_routes.
    assert: a single HTTP route covering both hostnames, attaching to both per-hostname HTTP listeners.
    """
    manager, mock = _make_http_route_manager()

    create_http_routes(
        manager,
        APP_NAME,
        GW_NAME,
        GW_MODEL,
        "disabled",
        ["a.example.com", "b.example.com"],
        PATHS,
        BACKEND_SVC,
        BACKEND_PORT,
    )

    applied = mock._applied
    assert len(applied) == 1
    assert applied[0].scheme == "http"
    assert applied[0].redirect_https is False
    assert set(applied[0].hostnames) == {"a.example.com", "b.example.com"}
    assert set(applied[0].listener_names) == {
        f"{GW_NAME}-http-a-example-com",
        f"{GW_NAME}-http-b-example-com",
    }


def test_create_http_routes_https_enabled_single_hostname():
    """
    arrange: https_mode=enabled, one hostname.
    act: call create_http_routes.
    assert: 2 routes created — 1 HTTP (all hostnames, no redirect) + 1 HTTPS (the hostname).
    """
    manager, mock = _make_http_route_manager()

    create_http_routes(
        manager,
        APP_NAME,
        GW_NAME,
        GW_MODEL,
        "enabled",
        ["app.example.com"],
        PATHS,
        BACKEND_SVC,
        BACKEND_PORT,
    )

    applied = mock._applied
    assert len(applied) == 2

    http_route = next(r for r in applied if r.scheme == "http")
    https_route = next(r for r in applied if r.scheme == "https")

    assert http_route.redirect_https is False
    assert http_route.listener_names == [f"{GW_NAME}-http-app-example-com"]
    assert http_route.hostnames == ["app.example.com"]
    assert https_route.listener_names == [f"{GW_NAME}-https-app-example-com"]
    assert https_route.hostnames == ["app.example.com"]


def test_create_http_routes_https_enabled_multiple_hostnames():
    """
    arrange: https_mode=enabled, two hostnames.
    act: call create_http_routes.
    assert: 3 routes — 1 HTTP covering both hostnames (attaching to both HTTP listeners)
        + 2 HTTPS each covering one hostname with its own per-hostname listener.
    """
    manager, mock = _make_http_route_manager()
    hostnames = ["alpha.example.com", "beta.example.com"]

    create_http_routes(
        manager,
        APP_NAME,
        GW_NAME,
        GW_MODEL,
        "enabled",
        hostnames,
        PATHS,
        BACKEND_SVC,
        BACKEND_PORT,
    )

    applied = mock._applied
    assert len(applied) == 3

    http_routes = [r for r in applied if r.scheme == "http"]
    https_routes = [r for r in applied if r.scheme == "https"]

    assert len(http_routes) == 1
    assert len(https_routes) == 2

    # HTTP route covers all hostnames and attaches to both per-hostname HTTP listeners
    assert set(http_routes[0].hostnames) == set(hostnames)
    assert set(http_routes[0].listener_names) == {
        f"{GW_NAME}-http-alpha-example-com",
        f"{GW_NAME}-http-beta-example-com",
    }

    # Each HTTPS route targets exactly one hostname with its own listener
    https_listener_names = {r.listener_names[0] for r in https_routes}
    assert https_listener_names == {
        f"{GW_NAME}-https-alpha-example-com",
        f"{GW_NAME}-https-beta-example-com",
    }
    https_hostname_sets = [set(r.hostnames) for r in https_routes]
    assert {"alpha.example.com"} in https_hostname_sets
    assert {"beta.example.com"} in https_hostname_sets

    for r in http_routes + https_routes:
        assert r.redirect_https is False


def test_create_http_routes_https_enforced_multiple_hostnames():
    """
    arrange: https_mode=enforced, two hostnames.
    act: call create_http_routes.
    assert: 3 routes — 1 HTTP redirect (all hostnames) + 2 HTTPS per hostname.
        The HTTP route has redirect_https=True; HTTPS routes have redirect_https=False.
    """
    manager, mock = _make_http_route_manager()
    hostnames = ["alpha.example.com", "beta.example.com"]

    create_http_routes(
        manager,
        APP_NAME,
        GW_NAME,
        GW_MODEL,
        "enforced",
        hostnames,
        PATHS,
        BACKEND_SVC,
        BACKEND_PORT,
    )

    applied = mock._applied
    assert len(applied) == 3

    http_routes = [r for r in applied if r.scheme == "http"]
    https_routes = [r for r in applied if r.scheme == "https"]

    assert len(http_routes) == 1
    assert len(https_routes) == 2

    assert http_routes[0].redirect_https is True
    assert set(http_routes[0].hostnames) == set(hostnames)

    for r in https_routes:
        assert r.redirect_https is False
        assert len(r.hostnames) == 1


def test_create_http_routes_empty_hostnames():
    """
    arrange: https_mode=enabled but hostnames=[].
    act: call create_http_routes.
    assert: only 1 HTTP route is created targeting the hostname-less HTTP listener
        (no HTTPS routes when there are no hostnames).
    """
    manager, mock = _make_http_route_manager()

    create_http_routes(
        manager,
        APP_NAME,
        GW_NAME,
        GW_MODEL,
        "enabled",
        [],
        PATHS,
        BACKEND_SVC,
        BACKEND_PORT,
    )

    applied = mock._applied
    assert len(applied) == 1
    assert applied[0].scheme == "http"
    assert applied[0].listener_names == [f"{GW_NAME}-http"]
