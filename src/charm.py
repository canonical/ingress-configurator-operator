#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import json
import logging
import typing
from functools import cached_property

import ops
from charms.haproxy.v1.haproxy_route_tcp import (
    HAPROXY_ROUTE_TCP_RELATION_NAME as HAPROXY_ROUTE_TCP_RELATION,
)
from charms.haproxy.v1.haproxy_route_tcp import (
    DataValidationError,
    HaproxyRouteTcpRequirer,
)
from charms.haproxy.v2.haproxy_route import HAPROXY_ROUTE_RELATION_NAME as HAPROXY_ROUTE_RELATION
from charms.haproxy.v2.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import DEFAULT_RELATION_NAME as INGRESS_RELATION
from charms.traefik_k8s.v2.ingress import IngressPerAppProvider
from lightkube import Client

from kubernetes import (
    delete_nodeport_services_owned_by,
    ensure_nodeport_service,
    get_kubernetes_data,
)
from state.haproxy_route import HaproxyRouteState, InvalidHaproxyRouteStateError
from state.haproxy_route_tcp import (
    HaproxyRouteTcpState,
    InvalidHaproxyRouteTcpStateError,
)

logger = logging.getLogger(__name__)
CREATED_BY_LABEL = "ingress-configurator.charm.juju.is/managed-by"


class IngressConfiguratorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Initialize the ingress-configurator charm.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self._lightkube_field_manager = self.app.name
        self._haproxy_route = HaproxyRouteRequirer(self, HAPROXY_ROUTE_RELATION)
        self._haproxy_route_tcp = HaproxyRouteTcpRequirer(self, HAPROXY_ROUTE_TCP_RELATION)

        self._ingress = IngressPerAppProvider(self)
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
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Action handlers
        self.framework.observe(self.on.get_proxied_endpoints_action, self._on_get_proxied_endpoint)

    @cached_property
    def lightkube_client(self) -> Client:
        """Returns a lightkube client configured for this charm."""
        return Client(namespace=self.model.name, field_manager=self._lightkube_field_manager)

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

        if sum([haproxy_route_related, haproxy_route_tcp_related]) > 1:
            logger.error("Mulltiple route relations exist.")
            self.unit.status = ops.BlockedStatus(
                "Only one route relation type should exist (haproxy-route or haproxy-route-tcp)."
            )
            return

        if haproxy_route_related:
            self._reconcile_haproxy_route()
        elif haproxy_route_tcp_related:
            self._reconcile_haproxy_route_tcp()
        else:
            self.unit.status = ops.BlockedStatus("Route relation required.")

    def _reconcile_haproxy_route(self) -> None:
        """Reconcile haproxy-route (HTTP) requirer data.

        Mode selection:
        - Guard: no ingress relation on Kubernetes → blocked (relation must be added).
        - Guard: ingress relation present but requirer not ready → wait for data.
        - Kubernetes adapter: ingress data available on Kubernetes substrate.
        - Adapter: ingress data available on a machine substrate.
        - Integrator: no ingress relation, backend addresses come from charm config.
        """
        ingress_relation = self.model.get_relation(self._ingress.relation_name)

        if ingress_relation is None and self.is_kubernetes():
            delete_nodeport_services_owned_by(self.lightkube_client, self.app.name)
            self.unit.status = ops.BlockedStatus(
                "Ingress relation required on Kubernetes substrate."
            )
            return

        if ingress_relation is not None and not self._ingress.is_ready():
            logger.info("Ingress relation exists but is not ready. Waiting for ingress data.")
            self.unit.status = ops.WaitingStatus("Waiting for ingress relation data.")
            return

        ingress_data = (
            self._ingress.get_data(ingress_relation) if ingress_relation is not None else None
        )

        if ingress_data is not None:  # Adapter mode
            if self.is_kubernetes():
                service_name = f"{self.model.name}-{self.app.name}-service"
                ensure_nodeport_service(
                    self.lightkube_client,
                    ingress_data.app.port,
                    service_name,
                    ingress_data.app.name,
                    self.app.name,
                )
                kubernetes_data = get_kubernetes_data(self.lightkube_client, service_name)
                try:
                    charm_state = HaproxyRouteState.for_kubernetes_adapter_mode(
                        self,
                        backend_addresses=kubernetes_data.backend_addresses,
                        backend_ports=[kubernetes_data.backend_port],
                        service=kubernetes_data.service_name,
                    )
                except InvalidHaproxyRouteStateError as exc:
                    logger.exception(
                        "Invalid haproxy-route configuration [adapter with k8s backend]."
                    )
                    self.unit.status = ops.BlockedStatus(str(exc))
                    return
            else:
                try:
                    charm_state = HaproxyRouteState.for_adapter_mode(self, ingress_data)
                except InvalidHaproxyRouteStateError as exc:
                    logger.exception("Invalid haproxy-route configuration [adapter].")
                    self.unit.status = ops.BlockedStatus(str(exc))
                    return
        else:  # Integrator mode
            try:
                charm_state = HaproxyRouteState.for_integrator_mode(self)
            except InvalidHaproxyRouteStateError as exc:
                logger.exception("Invalid haproxy-route configuration [integrator].")
                self.unit.status = ops.BlockedStatus(str(exc))
                return

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
            "retry_count": charm_state.retry.count if charm_state.retry else None,
            "retry_redispatch": charm_state.retry.redispatch if charm_state.retry else None,
            "server_timeout": charm_state.timeout.server,
            "connect_timeout": charm_state.timeout.connect,
            "queue_timeout": charm_state.timeout.queue,
            "service": charm_state.service,
            "hostname": charm_state.hostname,
            "additional_hostnames": charm_state.additional_hostnames,
            "load_balancing_algorithm": charm_state.load_balancing_configuration.algorithm,
            "load_balancing_cookie": charm_state.load_balancing_configuration.cookie,
            "load_balancing_consistent_hashing": charm_state.load_balancing_configuration.consistent_hashing,
            "http_server_close": charm_state.http_server_close,
            "path_rewrite_expressions": charm_state.path_rewrite_expressions,
            "header_rewrite_expressions": charm_state.header_rewrite_expressions,
            "allow_http": charm_state.allow_http,
            "external_grpc_port": charm_state.external_grpc_port,
        }
        not_none_params = {k: v for k, v in params.items() if v is not None}
        self._haproxy_route.provide_haproxy_route_requirements(**not_none_params)

        # Publish endpoints in adapter mode if ingress relation exists. In integrator mode.
        if ingress_relation and (proxied_endpoints := self._haproxy_route.get_proxied_endpoints()):
            self._ingress.publish_url(ingress_relation, str(proxied_endpoints[0]))
        self.unit.status = ops.ActiveStatus("Ready")

    def _reconcile_haproxy_route_tcp(self) -> None:
        """Reconcile haproxy-route-tcp requirer data."""
        if self.model.get_relation(self._ingress.relation_name) is not None:
            logger.error(
                "Cannot relate to both haproxy-route-tcp and ingress relations simultaneously."
            )
            self.unit.status = ops.BlockedStatus(
                "haproxy-route-tcp cannot be used with ingress relation. Use integrator mode only."
            )
            return

        try:
            tcp_requirements = HaproxyRouteTcpState.for_integrator_mode(self)
        except InvalidHaproxyRouteTcpStateError as exc:
            logger.exception("Invalid haproxy-route-tcp configuration [integrator].")
            self.unit.status = ops.BlockedStatus(str(exc))
            return

        try:
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
        except DataValidationError as exc:
            logger.exception("Error providing haproxy-route-tcp requirements.")
            self.unit.status = ops.BlockedStatus(str(exc))
            return
        self.unit.status = ops.ActiveStatus("Ready")

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


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
