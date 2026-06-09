# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for gateway-route support in the ingress configurator charm."""

import json
from typing import TYPE_CHECKING

import ops.testing
import pytest

if TYPE_CHECKING:
    from lightkube import Client as LightkubeClient

    from charm import IngressConfiguratorCharm

INGRESS_REMOTE_APP_DATA = {
    "model": '"testing-model"',
    "name": '"testing-app"',
    "port": "8080",
}
INGRESS_REMOTE_UNITS_DATA = {0: {"host": '"test.local"'}}

GATEWAY_ROUTE_PROVIDER_DATA = {
    "gateway_name": '"my-gateway"',
    "gateway_model": '"gateway-model"',
    "https_mode": '"enforced"',
    "endpoints": json.dumps(["https://example.com/app1"]),
}


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_happy_path(context_k8s: ops.testing.Context["IngressConfiguratorCharm"]):
    """
    arrange: both ingress and gateway-route relations with valid provider data.
    act: trigger config-changed.
    assert: status is Active("Ready"), requirer data written to gateway-route databag.
    """
    state = ops.testing.State(
        config={
            "hostname": "example.com",
            "paths": "/app1,/app2",
        },
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    gateway_rel_app_data: dict[str, str] = out.get_relations("gateway-route")[0].local_app_data
    assert gateway_rel_app_data["hostname"] == '"example.com"'
    assert "name" not in gateway_rel_app_data
    assert "model" not in gateway_rel_app_data
    assert "paths" not in gateway_rel_app_data
    assert "port" not in gateway_rel_app_data


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_no_hostname(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: gateway-route with no hostname configured.
    act: trigger config-changed.
    assert: status is Active — hostname is optional so routing uses additional-hostnames only.
    """
    state = ops.testing.State(
        config={"paths": "/"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_additional_hostnames_only(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: gateway-route with no primary hostname but with additional hostnames.
    act: trigger config-changed.
    assert: status is Active — routes are created using additional hostnames only.
    """
    state = ops.testing.State(
        config={"additional-hostnames": "app.example.com,api.example.com", "paths": "/"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_invalid_hostname(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: invalid hostname in config.
    act: trigger config-changed.
    assert: status is Blocked with message about invalid hostname.
    """
    state = ops.testing.State(
        config={"hostname": "not a valid hostname!"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "hostname" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_https_backend_protocol_blocked(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: backend-protocol set to https in gateway-route mode.
    act: trigger config-changed.
    assert: status is Blocked explaining that https backend is not supported.
    """
    state = ops.testing.State(
        config={"hostname": "example.com", "backend-protocol": "https"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "https" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_no_gateway_route_relation(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: only ingress relation (no gateway-route, no haproxy-route).
    act: trigger config-changed.
    assert: existing blocked status ("No valid mode detected.") is returned.
    """
    state = ops.testing.State(
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "Route relation required." in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_blocked_no_ingress_relation(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: gateway-route relation present but ingress relation missing.
    act: trigger config-changed.
    assert: status is Blocked("Ingress relation required.").
    """
    state = ops.testing.State(
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus("Ingress relation required.")


def test_gateway_route_https_mode_enforced(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"], mock_lightkube: "LightkubeClient"
):
    """
    arrange: provider publishes https_mode="enforced".
    act: trigger config-changed.
    assert: two HTTPRoute apply calls — HTTP route with 301 redirect, HTTPS route with backendRef.
    """
    state = ops.testing.State(
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data={
                    "gateway_name": '"my-gateway"',
                    "gateway_model": '"gateway-model"',
                    "https_mode": '"enforced"',
                    "endpoints": json.dumps([]),
                },
            ),
        ],
        leader=True,
    )

    context_k8s.run(context_k8s.on.config_changed(), state)

    assert mock_lightkube.apply.call_count == 2  # type: ignore[attr-defined]
    http_call, https_call = mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
    http_resource = http_call.args[0]
    https_resource = https_call.args[0]

    # HTTP route: 301 redirect to HTTPS, http-listener
    assert http_resource.metadata.name == "ingress-configurator-testing-app-http"
    assert http_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http"
    http_rule = http_resource.spec["rules"][0]
    assert http_rule["filters"][0]["type"] == "RequestRedirect"
    assert http_rule["filters"][0]["requestRedirect"]["scheme"] == "https"
    assert http_rule["filters"][0]["requestRedirect"]["statusCode"] == 301
    assert "backendRefs" not in http_rule

    # HTTPS route: forwards to backend, https-listener
    assert https_resource.metadata.name == "ingress-configurator-testing-app-https"
    assert https_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-https"
    https_rule = https_resource.spec["rules"][0]
    assert https_rule["backendRefs"][0]["port"] == 8080
    assert "filters" not in https_rule


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_wildcard_hostname_blocked(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: wildcard hostname in config.
    act: trigger config-changed.
    assert: status is Blocked with message about invalid hostname.
    """
    state = ops.testing.State(
        config={"hostname": "*.example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "hostname" in out.unit_status.message


def test_gateway_route_https_mode_disabled(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"], mock_lightkube: "LightkubeClient"
):
    """
    arrange: provider publishes https_mode="disabled".
    act: trigger config-changed.
    assert: one HTTPRoute apply call with HTTP-only backendRef, no redirect.
    """
    state = ops.testing.State(
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data={
                    "gateway_name": '"my-gateway"',
                    "gateway_model": '"gateway-model"',
                    "https_mode": '"disabled"',
                    "endpoints": json.dumps([]),
                },
            ),
        ],
        leader=True,
    )

    context_k8s.run(context_k8s.on.config_changed(), state)

    assert mock_lightkube.apply.call_count == 1  # type: ignore[attr-defined]
    (single_call,) = mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
    resource = single_call.args[0]

    assert resource.metadata.name == "ingress-configurator-testing-app-http"
    assert resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http"
    rule = resource.spec["rules"][0]
    assert rule["backendRefs"][0]["port"] == 8080
    assert "filters" not in rule
    assert resource.spec.get("hostnames") == ["example.com"]


def test_gateway_route_https_mode_enabled(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"], mock_lightkube: "LightkubeClient"
):
    """
    arrange: provider publishes https_mode="enabled".
    act: trigger config-changed.
    assert: two HTTPRoute apply calls, both forwarding to backend (no redirect), on their respective listeners.
    """
    state = ops.testing.State(
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data={
                    "gateway_name": '"my-gateway"',
                    "gateway_model": '"gateway-model"',
                    "https_mode": '"enabled"',
                    "endpoints": json.dumps([]),
                },
            ),
        ],
        leader=True,
    )

    context_k8s.run(context_k8s.on.config_changed(), state)

    assert mock_lightkube.apply.call_count == 2  # type: ignore[attr-defined]
    http_call, https_call = mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
    http_resource = http_call.args[0]
    https_resource = https_call.args[0]

    # Both routes forward to the backend
    assert http_resource.metadata.name == "ingress-configurator-testing-app-http"
    assert http_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http"
    http_rule = http_resource.spec["rules"][0]
    assert http_rule["backendRefs"][0]["port"] == 8080
    assert "filters" not in http_rule

    assert https_resource.metadata.name == "ingress-configurator-testing-app-https"
    assert https_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-https"
    https_rule = https_resource.spec["rules"][0]
    assert https_rule["backendRefs"][0]["port"] == 8080
    assert "filters" not in https_rule


def test_gateway_route_blocked_on_machine_substrate(
    context_machine: ops.testing.Context["IngressConfiguratorCharm"],
):
    """
    arrange: create a context with a machine_id set (non-Kubernetes substrate)
        and a gateway-route relation.
    act: trigger a config-changed event.
    assert: unit status is blocked with the appropriate message.
    """
    state = ops.testing.State(
        relations=[ops.testing.Relation("gateway-route")],
        leader=True,
    )

    out = context_machine.run(context_machine.on.config_changed(), state)

    assert out.unit_status == ops.testing.BlockedStatus(
        "ingress-configurator can only be deployed on Kubernetes when integrated with gateway-route."
    )


@pytest.mark.usefixtures("mock_lightkube")
@pytest.mark.parametrize(
    "provider_app_data",
    [
        pytest.param({}, id="empty-databag"),
        pytest.param(
            {
                "gateway_name": '"my-gateway"',
                "gateway_model": '"gateway-model"',
                "https_mode": '"not-a-valid-mode"',
            },
            id="invalid-https-mode",
        ),
    ],
)
def test_gateway_route_waiting_for_invalid_provider_data(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    provider_app_data: dict,
):
    """
    arrange: gateway-route relation present with an empty or invalid provider databag.
    act: trigger config-changed.
    assert: status is Waiting("Invalid gateway-route provider data").
    """
    state = ops.testing.State(
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_REMOTE_APP_DATA,
                remote_units_data=INGRESS_REMOTE_UNITS_DATA,
            ),
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=provider_app_data,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.WaitingStatus("Invalid gateway-route provider data")
