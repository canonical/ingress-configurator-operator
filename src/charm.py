#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import json
import logging
import typing

import ops
from charms.gateway_api_integrator.v1.gateway_route import (
    GatewayRouteInvalidRelationDataError,
    GatewayRouteRequirer,
)
from charms.haproxy.v1.haproxy_route_tcp import DataValidationError, HaproxyRouteTcpRequirer
from charms.haproxy.v2.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppProvider
from lightkube import Client

from gateway_route import (
    HTTPRouteConfig,
    HTTPRouteManager,
    InsufficientPermissionError,
)
from kubernetes import (
    delete_nodeport_services_owned_by,
    ensure_nodeport_service,
    get_kubernetes_data,
)
from state.charm_state import InvalidStateError, State
from state.gateway_route import GatewayRouteState, InvalidGatewayRouteStateError
from state.haproxy_route_tcp import (
    HaproxyRouteTcpRequirements,
    InvalidHaproxyRouteTcpRequirementsError,
)

logger = logging.getLogger(__name__)
HAPROXY_ROUTE_RELATION = "haproxy-route"
HAPROXY_ROUTE_TCP_RELATION = "haproxy-route-tcp"
INGRESS_RELATION = "ingress"
GATEWAY_ROUTE_RELATION = "gateway-route"
CREATED_BY_LABEL = "ingress-configurator.charm.juju.is/managed-by"


class ProvideHaproxyRouteTcpRequirementsError(Exception):
    """Exception raised when providing HAProxy TCP route requirements fails."""


class IngressConfiguratorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Initialize the ingress-configurator charm.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self._lightkube_client: Client | None = None
        self._lightkube_field_manager = self.app.name
        self._haproxy_route = HaproxyRouteRequirer(self, HAPROXY_ROUTE_RELATION)
        self._haproxy_route_tcp = HaproxyRouteTcpRequirer(self, HAPROXY_ROUTE_TCP_RELATION)
        self._gateway_route = GatewayRouteRequirer(self, relation_name=GATEWAY_ROUTE_RELATION)

        self._ingress = IngressPerAppProvider(self, INGRESS_RELATION)
        self.framework.observe(self.on.config_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_broken, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_departed, self._reconcile)
        self.framework.observe(
            self.on[HAPROXY_ROUTE_TCP_RELATION].relation_changed, self._reconcile
        )
        self.framework.observe(
            self.on[HAPROXY_ROUTE_TCP_RELATION].relation_broken, self._reconcile
        )
        self.framework.observe(
            self.on[HAPROXY_ROUTE_TCP_RELATION].relation_departed, self._reconcile
        )
        self.framework.observe(self.on[INGRESS_RELATION].relation_broken, self._reconcile)
        self.framework.observe(self.on[INGRESS_RELATION].relation_departed, self._reconcile)
        self.framework.observe(self.on[INGRESS_RELATION].relation_changed, self._reconcile)
        self.framework.observe(self.on[GATEWAY_ROUTE_RELATION].relation_changed, self._reconcile)
        self.framework.observe(self.on[GATEWAY_ROUTE_RELATION].relation_broken, self._reconcile)
        self.framework.observe(self.on[GATEWAY_ROUTE_RELATION].relation_departed, self._reconcile)
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Action handlers
        self.framework.observe(self.on.get_proxied_endpoints_action, self._on_get_proxied_endpoint)

    @property
    def lightkube_client(self) -> Client:
        """Returns a lightkube client configured for this charm."""
        if self._lightkube_client is None:
            self._lightkube_client = Client(
                namespace=self.model.name, field_manager=self._lightkube_field_manager
            )
        return self._lightkube_client

    def is_kubernetes(self) -> bool:
        """Return True if the charm is running on a Kubernetes substrate.

        On machine substrates Juju sets the JUJU_MACHINE_ID environment
        variable, which is surfaced as :attr:`ops.JujuContext.machine_id`.
        On Kubernetes that variable is absent, so ``machine_id`` is ``None``.

        Returns:
            True when running on Kubernetes, False on a machine substrate.
        """
        return self.model._backend._juju_context.machine_id is None

    def _reconcile(self, _: ops.EventBase) -> None:
        """Dispatch to the appropriate reconcile method based on active relations."""
        haproxy_route_related = self._haproxy_route.relation is not None
        haproxy_route_tcp_related = self._haproxy_route_tcp.relation is not None
        haproxy_related = haproxy_route_related or haproxy_route_tcp_related
        gateway_route_related = self._gateway_route.relation is not None

        if haproxy_related and gateway_route_related:
            self.unit.status = ops.BlockedStatus(
                "Only one route relation type should exist (haproxy-route/haproxy-route-tcp or gateway-route)."
            )
            return

        if gateway_route_related:
            self._reconcile_gateway_route()
        elif haproxy_related:
            self._reconcile_haproxy()
        else:
            self.unit.status = ops.BlockedStatus("Route relation required.")

    def _reconcile_haproxy(self) -> None:
        """Reconcile haproxy-route and haproxy-route-tcp requirer data."""
        try:
            if self._haproxy_route.relation is not None:
                self._reconcile_haproxy_http()
            if self._haproxy_route_tcp.relation is not None:
                self._reconcile_haproxy_tcp()
            self.unit.status = ops.ActiveStatus()
        except InvalidStateError as exc:
            logger.exception("Invalid haproxy-route configuration.")
            self.unit.status = ops.BlockedStatus(str(exc))
        except ProvideHaproxyRouteTcpRequirementsError:
            logger.exception("Error providing haproxy-route-tcp requirements.")
            self.unit.status = ops.BlockedStatus(
                "Error updating haproxy-route-tcp relation data, check your configuration."
            )

    def _reconcile_haproxy_http(self) -> None:
        """Reconcile haproxy-route (HTTP) requirer data.

        Raises:
            InvalidStateError: When the charm state is invalid.
        """
        ingress_relation_data = None
        ingress_relation = self.model.get_relation(self._ingress.relation_name)
        if self._ingress.is_ready():
            ingress_relation_data = (
                self._ingress.get_data(ingress_relation) if ingress_relation else None
            )
        kubernetes_data = None
        if self.is_kubernetes() and ingress_relation_data is not None:
            service_name = f"{self.model.name}-{self.app.name}-service"
            ensure_nodeport_service(
                self.lightkube_client,
                ingress_relation_data.app.port,
                service_name,
                ingress_relation_data.app.name,
                self.app.name,
            )
            kubernetes_data = get_kubernetes_data(
                self.lightkube_client,
                service_name,
            )
        elif self.is_kubernetes() and ingress_relation_data is None:
            delete_nodeport_services_owned_by(self.lightkube_client, self.app.name)
        charm_state = State.from_charm(self, ingress_relation_data, kubernetes_data)
        # Assign consistent_hashing to a local variable due to line length limit
        consistent_hashing = charm_state.load_balancing_configuration.consistent_hashing
        params = {
            "hosts": [str(address) for address in charm_state.backend_addresses],
            "check_interval": charm_state.health_check.interval,
            "check_rise": charm_state.health_check.rise,
            "check_fall": charm_state.health_check.fall,
            "check_path": charm_state.health_check.path,
            "check_port": charm_state.health_check.port,
            "paths": charm_state.paths,
            "ports": charm_state.backend_ports,
            "protocol": charm_state.backend_protocol,
            "retry_count": charm_state.retry.count,
            "retry_redispatch": charm_state.retry.redispatch,
            "server_timeout": charm_state.timeout.server,
            "connect_timeout": charm_state.timeout.connect,
            "queue_timeout": charm_state.timeout.queue,
            "service": charm_state.service,
            "hostname": charm_state.hostname,
            "additional_hostnames": charm_state.additional_hostnames,
            "load_balancing_algorithm": charm_state.load_balancing_configuration.algorithm,
            "load_balancing_cookie": charm_state.load_balancing_configuration.cookie,
            "load_balancing_consistent_hashing": consistent_hashing,
            "http_server_close": charm_state.http_server_close,
            "path_rewrite_expressions": charm_state.path_rewrite_expressions,
            "header_rewrite_expressions": charm_state.header_rewrite_expressions,
            "allow_http": charm_state.allow_http,
            "external_grpc_port": charm_state.external_grpc_port,
        }
        not_none_params = {k: v for k, v in params.items() if v is not None}
        self._haproxy_route.provide_haproxy_route_requirements(**not_none_params)
        proxied_endpoints = self._haproxy_route.get_proxied_endpoints()
        if ingress_relation and proxied_endpoints:
            self._ingress.publish_url(ingress_relation, str(proxied_endpoints[0]))

    def _reconcile_haproxy_tcp(self) -> None:
        """Reconcile haproxy-route-tcp requirer data.

        Raises:
            ProvideHaproxyRouteTcpRequirementsError: When providing TCP requirements fails.
        """
        self._provide_haproxy_route_tcp_requirements()

    def _reconcile_gateway_route(self) -> None:
        """Reconcile gateway-route: create HTTPRoute resources and update relation data."""
        if not self.is_kubernetes():
            self.unit.status = ops.BlockedStatus(
                "gateway-route relation only supported on Kubernetes."
            )
            return

        ingress_relation = self.model.get_relation(self._ingress.relation_name)
        # Only support through ingress relation for now, so if it's missing or not ready we can't proceed with gateway-route configuration
        if not ingress_relation:
            return

        if not self._ingress.is_ready():
            self.unit.status = ops.WaitingStatus("Waiting for ingress relation data")
            return

        try:
            ingress_data = self._ingress.get_data(ingress_relation)
        except DataValidationError:
            self.unit.status = ops.BlockedStatus("Invalid ingress relation data")
            return

        # Since we have not yet implemented support in integration mode,
        # we cannot fall back to it when the ports are closed, so we block instead for now.
        if not ingress_data.app.is_port_open:
            logger.error(
                "Workload ports are not open according to ingress relation data. "
            )
            self.unit.status = ops.BlockedStatus(
                "Support for backends with closed ports not yet implemented"
            )
            return

        try:
            state = GatewayRouteState.from_charm(self, ingress_data)
        except InvalidGatewayRouteStateError as exc:
            self.unit.status = ops.BlockedStatus(str(exc))
            return

        self.unit.status = ops.MaintenanceStatus("Configuring gateway route")

        try:
            self._gateway_route.publish_requirer_data(
                hostname=state.hostname,
                additional_hostnames=list(state.additional_hostnames),
            )
        except GatewayRouteInvalidRelationDataError as exc:
            logger.exception("Invalid gateway-route relation data.")
            self.unit.status = ops.BlockedStatus(str(exc))
            return

        provider_data = None
        try:
            provider_data = self._gateway_route.get_provider_data()
        except GatewayRouteInvalidRelationDataError:
            logger.exception("Invalid gateway-route provider data.")
            self.unit.status = ops.BlockedStatus("Invalid gateway-route provider data")
        if provider_data is None:
            self.unit.status = ops.WaitingStatus("Waiting for gateway-route provider data")
            return

        gateway_relation = self._gateway_route.relation
        raw_provider = gateway_relation.data[gateway_relation.app]  # type: ignore[union-attr]

        manager = HTTPRouteManager(
            client=self.lightkube_client,
            namespace=self.model.name,
            labels={CREATED_BY_LABEL: self.app.name},
        )
        try:
            self._create_http_routes(
                http_route_manager=manager,
                gateway_name=provider_data.gateway_name,
                gateway_model=provider_data.model_name,
                https_mode=provider_data.https_mode,
                hostnames=state.hostnames,
                paths=state.paths,
                backend_service_name=state.application_name,
                backend_service_port=state.port,
            )
        except InsufficientPermissionError as exc:
            self.unit.status = ops.BlockedStatus(str(exc))
            return

        raw_endpoints_json = raw_provider.get("endpoints", "[]")
        try:
            endpoints = json.loads(raw_endpoints_json)
        except json.JSONDecodeError:
            endpoints = []

        if endpoints:
            self._ingress.publish_url(ingress_relation, url=str(endpoints[0]))
            self.unit.status = ops.ActiveStatus("Ready")
        else:
            self.unit.status = ops.ActiveStatus()

    def _create_http_routes(
        self,
        http_route_manager: HTTPRouteManager,
        gateway_name: str,
        gateway_model: str,
        https_mode: str,
        hostnames: list[str],
        paths: list[str],
        backend_service_name: str,
        backend_service_port: int,
    ) -> None:
        """Create HTTPRoute K8s resources based on https_mode.

        Args:
            http_route_manager: The HTTPRouteManager to apply and clean up resources.
            gateway_name: Name of the Gateway K8s resource.
            gateway_namespace: Namespace of the Gateway resource.
            https_mode: One of "disabled", "enabled", "enforced".
            hostnames: List of hostnames for the HTTPRoute.
            paths: List of path prefixes.
            backend_service_name: Name of the backend K8s Service.
            backend_service_port: Port of the backend Service.
        """
        managed_names = []
        route_base_name = f"{self.app.name}-{backend_service_name}"
        http_listener = f"{gateway_name}-http"
        https_listener = f"{gateway_name}-https"

        if https_mode == "disabled":
            config = HTTPRouteConfig(
                name=f"{route_base_name}-http",
                gateway_name=gateway_name,
                gateway_namespace=gateway_model,
                listener_name=http_listener,
                hostnames=hostnames,
                paths=paths,
                backend_service_name=backend_service_name,
                backend_service_port=backend_service_port,
            )
            managed_names.append(http_route_manager.apply(config))

        elif https_mode == "enabled":
            for scheme, listener in (("http", http_listener), ("https", https_listener)):
                config = HTTPRouteConfig(
                    name=f"{route_base_name}-{scheme}",
                    gateway_name=gateway_name,
                    gateway_namespace=gateway_model,
                    listener_name=listener,
                    hostnames=hostnames,
                    paths=paths,
                    backend_service_name=backend_service_name,
                    backend_service_port=backend_service_port,
                )
                managed_names.append(http_route_manager.apply(config))

        elif https_mode == "enforced":
            redirect_config = HTTPRouteConfig(
                name=f"{route_base_name}-http",
                gateway_name=gateway_name,
                gateway_namespace=gateway_model,
                listener_name=http_listener,
                hostnames=hostnames,
                paths=paths,
                backend_service_name=backend_service_name,
                backend_service_port=backend_service_port,
                redirect_https=True,
            )
            managed_names.append(http_route_manager.apply(redirect_config))
            https_config = HTTPRouteConfig(
                name=f"{route_base_name}-https",
                gateway_name=gateway_name,
                gateway_namespace=gateway_model,
                listener_name=https_listener,
                hostnames=hostnames,
                paths=paths,
                backend_service_name=backend_service_name,
                backend_service_port=backend_service_port,
            )
            managed_names.append(http_route_manager.apply(https_config))

        http_route_manager.delete_stale(exclude=managed_names)

    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        """Periodically refresh node IPs and reconcile the NodePort service.

        On Kubernetes substrates, node IPs can change over time. This handler
        ensures the haproxy-route relation data stays in sync with the current
        cluster state by delegating to the standard reconcile flow.
        """
        if not self.is_kubernetes():
            return
        self._reconcile(event)

    def _on_get_proxied_endpoint(self, event: ops.ActionEvent) -> None:
        """Handle the get_proxied_endpoints action."""
        haproxy_relation = self._haproxy_route.relation
        if not haproxy_relation:
            event.fail("Missing haproxy-route relation.")
            return

        endpoints = [str(endpoint) for endpoint in self._haproxy_route.get_proxied_endpoints()]
        result = {"endpoints": json.dumps(endpoints) if endpoints else {}}

        event.set_results(result)

    def _provide_haproxy_route_tcp_requirements(self) -> None:
        """Provide HAProxy TCP route requirements to the requirer."""
        try:
            tcp_requirements = HaproxyRouteTcpRequirements.from_charm(self)
            self._haproxy_route_tcp.provide_haproxy_route_tcp_requirements(
                hosts=tcp_requirements.backend_addresses,
                port=tcp_requirements.port,
                backend_port=tcp_requirements.backend_port,
                tls_terminate=tcp_requirements.tls_terminate,
                sni=tcp_requirements.hostname,
                retry_count=tcp_requirements.retry.count,
                retry_redispatch=tcp_requirements.retry.redispatch or False,
                load_balancing_algorithm=tcp_requirements.load_balancing_configuration.algorithm,
                load_balancing_consistent_hashing=(
                    tcp_requirements.load_balancing_configuration.consistent_hashing
                ),
                enforce_tls=tcp_requirements.enforce_tls,
                check_interval=tcp_requirements.health_check.interval,
                check_rise=tcp_requirements.health_check.rise,
                check_fall=tcp_requirements.health_check.fall,
                check_type=tcp_requirements.health_check.check_type,
                check_send=tcp_requirements.health_check.send,
                check_expect=tcp_requirements.health_check.expect,
                check_db_user=tcp_requirements.health_check.db_user,
                server_timeout=tcp_requirements.timeout.server,
                connect_timeout=tcp_requirements.timeout.connect,
                queue_timeout=tcp_requirements.timeout.queue,
                proxy_protocol=tcp_requirements.proxy_protocol,
            )
        except (InvalidHaproxyRouteTcpRequirementsError, DataValidationError) as exc:
            raise ProvideHaproxyRouteTcpRequirementsError(
                "Failed to provide haproxy-route-tcp requirements."
            ) from exc


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
