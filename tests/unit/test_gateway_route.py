# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for gateway-route support in the ingress configurator charm."""

import json
from typing import TYPE_CHECKING
from unittest.mock import ANY

import ops.testing
import pytest

if TYPE_CHECKING:
    from lightkube import Client as LightkubeClient

    from charm import IngressConfiguratorCharm

INGRESS_REMOTE_APP_DATA = {
    "model": '"testing-model"',
    "name": '"testing-app"',
    "port": "8080",
    "is_port_open": "true",
}
INGRESS_REMOTE_UNITS_DATA = {0: {"host": '"test.local"', "ip": '"10.0.0.1"'}}

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
    assert "backend_protocol" in out.unit_status.message


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

    assert out.unit_status == ops.testing.BlockedStatus(
        "Ingress relation or backend config required."
    )


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
    assert http_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http-listener"
    http_rule = http_resource.spec["rules"][0]
    assert http_rule["filters"][0]["type"] == "RequestRedirect"
    assert http_rule["filters"][0]["requestRedirect"]["scheme"] == "https"
    assert http_rule["filters"][0]["requestRedirect"]["statusCode"] == 301
    assert "backendRefs" not in http_rule

    # HTTPS route: forwards to backend, https-listener
    assert https_resource.metadata.name == "ingress-configurator-testing-app-https"
    assert https_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-https-listener"
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
    assert resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http-listener"
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
    assert http_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-http-listener"
    http_rule = http_resource.spec["rules"][0]
    assert http_rule["backendRefs"][0]["port"] == 8080
    assert "filters" not in http_rule

    assert https_resource.metadata.name == "ingress-configurator-testing-app-https"
    assert https_resource.spec["parentRefs"][0]["sectionName"] == "my-gateway-https-listener"
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


# ---------------------------------------------------------------------------
# Adapter mode: port closed blocks
# ---------------------------------------------------------------------------

INGRESS_PORT_CLOSED_APP_DATA = {
    "model": '"testing-model"',
    "name": '"testing-app"',
    "port": "8080",
    "is_port_open": "false",
}
INGRESS_PORT_CLOSED_UNITS_DATA = {0: {"host": '"test.local"', "ip": '"10.0.0.1"'}}


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_adapter_port_closed_creates_selector_service(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube: "LightkubeClient",
) -> None:
    """
    arrange: ingress relation with is_port_open=False.
    act: trigger config-changed.
    assert: status is Active("Ready"); a selector Service is created with the
        target app's pod selector and the backend port; the HTTPRoute backendRef
        uses the selector Service name, not the requirer app name.
    """
    from lightkube.resources.core_v1 import Service

    from http_route import MANAGED_BY_LABEL

    state = ops.testing.State(
        config={"hostname": "example.com"},
        relations=[
            ops.testing.Relation(
                endpoint="ingress",
                remote_app_data=INGRESS_PORT_CLOSED_APP_DATA,
                remote_units_data=INGRESS_PORT_CLOSED_UNITS_DATA,
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

    apply_calls = mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
    svc_calls = [c for c in apply_calls if isinstance(c.args[0], Service)]
    assert len(svc_calls) == 1
    svc: Service = svc_calls[0].args[0]
    assert svc.metadata is not None
    assert svc.metadata.name == "ingress-configurator-testing-app"
    assert svc.metadata.labels is not None
    assert svc.metadata.labels.get(MANAGED_BY_LABEL) == "ingress-configurator"
    assert svc.spec is not None
    assert svc.spec.selector == {"app.kubernetes.io/name": "testing-app"}
    assert svc.spec.ports is not None
    assert svc.spec.ports[0].port == 8080


def test_gateway_route_port_open_cleans_up_stale_headless_resources(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube: "LightkubeClient",
) -> None:
    """
    arrange: ingress relation with is_port_open=True; mock client.list returns a
        stale headless Service left over from a previous integrator mode run.
    act: trigger config-changed.
    assert: status is Active; the stale headless Service is deleted.
    """
    from unittest.mock import MagicMock

    from lightkube.resources.core_v1 import Service

    from http_route import MANAGED_BY_LABEL

    stale_svc = MagicMock()
    stale_svc.metadata.name = "ingress-configurator-headless"

    def list_side_effect(resource_type: type, labels: dict | None = None, **_: object) -> list:
        if (
            resource_type is Service
            and labels
            and labels.get(MANAGED_BY_LABEL) == "ingress-configurator"
        ):
            return [stale_svc]
        return []

    mock_lightkube.list.side_effect = list_side_effect  # type: ignore[attr-defined]

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
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")
    mock_lightkube.delete.assert_called_once_with(  # type: ignore[attr-defined]
        Service, name="ingress-configurator-headless", namespace=ANY
    )


# ---------------------------------------------------------------------------
# Integrator mode tests
# ---------------------------------------------------------------------------

GATEWAY_ROUTE_INTEGRATOR_CONFIG: dict[str, str | int | float | bool] = {
    "hostname": "example.com",
    "backend-addresses": "10.0.0.1,10.0.0.2",
    "backend-ports": "8080",
}


def test_gateway_route_integrator_happy_path(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube: "LightkubeClient",
) -> None:
    """
    arrange: no ingress relation; backend-addresses (IPv4 IPs) and single backend-ports
        set in config; gateway-route relation with valid provider data.
    act: trigger config-changed.
    assert: status is Active; headless Service and EndpointSlice (addressType=IPv4,
        IP endpoints) are applied; HTTPRoute backend references the headless Service.
    """
    from lightkube.resources.core_v1 import Service
    from lightkube.resources.discovery_v1 import EndpointSlice

    from http_route import MANAGED_BY_LABEL

    state = ops.testing.State(
        config=GATEWAY_ROUTE_INTEGRATOR_CONFIG,
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")

    apply_calls = mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
    applied_types = [type(call.args[0]) for call in apply_calls]

    assert Service in applied_types, "headless Service was not applied"
    assert EndpointSlice in applied_types, "EndpointSlice was not applied"

    svc = next(call.args[0] for call in apply_calls if isinstance(call.args[0], Service))
    assert svc.metadata is not None
    assert svc.spec is not None
    assert svc.metadata.name == "ingress-configurator-headless"
    assert svc.spec.clusterIP == "None"
    assert svc.metadata.labels is not None
    assert svc.metadata.labels.get(MANAGED_BY_LABEL) == "ingress-configurator"

    es = next(call.args[0] for call in apply_calls if isinstance(call.args[0], EndpointSlice))
    assert es.addressType == "IPv4"
    endpoint_addrs = [ep.addresses[0] for ep in es.endpoints]
    assert "10.0.0.1" in endpoint_addrs
    assert "10.0.0.2" in endpoint_addrs
    assert es.metadata is not None
    assert es.metadata.labels is not None
    assert es.metadata.labels.get("kubernetes.io/service-name") == "ingress-configurator-headless"

    headless_name = "ingress-configurator-headless"
    http_route_calls = [
        call for call in apply_calls if type(call.args[0]) not in (Service, EndpointSlice)
    ]
    assert http_route_calls, "no HTTPRoute was applied"
    for call in http_route_calls:
        resource = call.args[0]
        backend_ref = resource.spec["rules"][0].get("backendRefs")
        if backend_ref is not None:
            assert backend_ref[0]["name"] == headless_name


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_integrator_blocked_ambiguous(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
) -> None:
    """
    arrange: both ingress relation and backend-addresses config set simultaneously.
    act: trigger config-changed.
    assert: status is Blocked about only one mode at a time.
    """
    state = ops.testing.State(
        config=GATEWAY_ROUTE_INTEGRATOR_CONFIG,
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

    assert out.unit_status == ops.testing.BlockedStatus(
        "Remove backend config or the ingress relation - only one can be used at a time."
    )


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_integrator_fqdn_rejected(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
) -> None:
    """
    arrange: backend-addresses contains an FQDN instead of an IP.
    act: trigger config-changed.
    assert: status is Blocked with a message about invalid IP address.
    """
    state = ops.testing.State(
        config={
            "hostname": "example.com",
            "backend-addresses": "backend.example.com",
            "backend-ports": "8080",
        },
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "backend_addresses" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_integrator_multiple_ports_blocked(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
) -> None:
    """
    arrange: backend-ports contains multiple values.
    act: trigger config-changed.
    assert: status is Blocked requiring exactly one port.
    """
    state = ops.testing.State(
        config={
            "hostname": "example.com",
            "backend-addresses": "10.0.0.1",
            "backend-ports": "8080,9090",
        },
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "exactly one port" in out.unit_status.message


@pytest.mark.usefixtures("mock_lightkube")
def test_gateway_route_integrator_mixed_ip_families_blocked(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
) -> None:
    """
    arrange: backend-addresses mixes IPv4 and IPv6 addresses.
    act: trigger config-changed.
    assert: status is Blocked about mixed IP families.
    """
    state = ops.testing.State(
        config={
            "hostname": "example.com",
            "backend-addresses": "10.0.0.1,::1",
            "backend-ports": "8080",
        },
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert isinstance(out.unit_status, ops.testing.BlockedStatus)
    assert "backend_addresses" in out.unit_status.message


def test_gateway_route_integrator_ipv6(
    context_k8s: ops.testing.Context["IngressConfiguratorCharm"],
    mock_lightkube: "LightkubeClient",
) -> None:
    """
    arrange: backend-addresses contains IPv6 addresses.
    act: trigger config-changed.
    assert: status is Active; EndpointSlice has addressType=IPv6.
    """
    from lightkube.resources.discovery_v1 import EndpointSlice

    state = ops.testing.State(
        config={
            "hostname": "example.com",
            "backend-addresses": "::1,::2",
            "backend-ports": "8080",
        },
        relations=[
            ops.testing.Relation(
                endpoint="gateway-route",
                remote_app_data=GATEWAY_ROUTE_PROVIDER_DATA,
            ),
        ],
        leader=True,
    )

    out = context_k8s.run(context_k8s.on.config_changed(), state)

    assert out.unit_status == ops.testing.ActiveStatus("Ready")

    es_calls = [
        call
        for call in mock_lightkube.apply.call_args_list  # type: ignore[attr-defined]
        if isinstance(call.args[0], EndpointSlice)
    ]
    assert es_calls, "no EndpointSlice was applied"
    assert es_calls[0].args[0].addressType == "IPv6"
