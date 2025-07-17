#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import logging
import typing

import ops
from charms.haproxy.v1.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppProvider

import state

logger = logging.getLogger(__name__)
HAPROXY_ROUTE_RELATION = "haproxy-route"
INGRESS_RELATION = "ingress"


class IngressConfiguratorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Initialize the ingress-configurator charm.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self._haproxy_route = HaproxyRouteRequirer(self, HAPROXY_ROUTE_RELATION)
        self._ingress = IngressPerAppProvider(self, INGRESS_RELATION)
        self.framework.observe(self.on.config_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_broken, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_departed, self._reconcile)
        self.framework.observe(self._ingress.on.data_provided, self._reconcile)
        self.framework.observe(self._ingress.on.data_removed, self._reconcile)

    def _reconcile(self, _: ops.EventBase) -> None:
        """Refresh haproxy-route requirer data."""
        try:
            if not self._haproxy_route.relation:
                self.unit.status = ops.BlockedStatus("Missing haproxy-route relation.")
                return
            ingress_relation = self.model.get_relation(self._ingress.relation_name)
            ingress_relation_data = (
                self._ingress.get_data(ingress_relation) if ingress_relation else None
            )
            charm_state = state.State.from_charm(self, ingress_relation_data)
            params = {
                "hosts": [str(address) for address in charm_state.backend_addresses],
                "check_interval": charm_state.health_check.interval,
                "check_rise": charm_state.health_check.rise,
                "check_fall": charm_state.health_check.fall,
                "check_path": charm_state.health_check.path,
                "check_port": charm_state.health_check.port,
                "paths": charm_state.paths,
                "ports": charm_state.backend_ports,
                "retry_count": charm_state.retry.count,
                "retry_interval": charm_state.retry.interval,
                "retry_redispatch": charm_state.retry.redispatch,
                "server_timeout": charm_state.timeout.server,
                "connect_timeout": charm_state.timeout.connect,
                "queue_timeout": charm_state.timeout.queue,
                "service": charm_state.service,
                "hostname": charm_state.hostname,
                "additional_hostnames": charm_state.additional_hostnames,
            }
            not_none_params = {k: v for k, v in params.items() if v is not None}
            self._haproxy_route.provide_haproxy_route_requirements(**not_none_params)
            proxied_endpoints = self._haproxy_route.get_proxied_endpoints()
            if ingress_relation and proxied_endpoints:
                self._ingress.publish_url(ingress_relation, proxied_endpoints[0])
            self.unit.status = ops.ActiveStatus()
        except state.InvalidStateError as ex:
            logger.exception("Invalid configuration")
            self.unit.status = ops.BlockedStatus(str(ex))


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
