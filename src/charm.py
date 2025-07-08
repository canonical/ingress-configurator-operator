#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import logging
import typing

import ops
from charms.haproxy.v0.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppProvider

from state import configurator

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
            mode = configurator.get_mode(
                self, self.model.get_relation(self._ingress.relation_name)
            )
            if not self._haproxy_route.relation:
                self.unit.status = ops.BlockedStatus("Missing haproxy-route relation.")
                return
            if mode == configurator.Mode.INTEGRATOR:
                integrator_information = configurator.IntegratorInformation.from_charm(self)
                self._haproxy_route.provide_haproxy_route_requirements(
                    service=f"{self.model.name}-{self.app.name}",
                    ports=[integrator_information.backend_port],
                    unit_address=str(integrator_information.backend_address),
                )
            elif mode == configurator.Mode.ADAPTER:
                relation = self.model.get_relation(self._ingress.relation_name)
                data = self._ingress.get_data(relation)
                self._haproxy_route.provide_haproxy_route_requirements(
                    service=f"{data.app.model}-{data.app.name}",
                    ports=[data.app.port],
                    unit_address=str([udata.host for udata in data.units][0]),
                )
            self.unit.status = ops.ActiveStatus()
        except configurator.UndefinedModeError:
            logger.exception("Invalid mode")
            self.unit.status = ops.BlockedStatus("Mode is invalid.")
        except configurator.InvalidIntegratorConfigError as ex:
            logger.exception("Invalid configuration")
            self.unit.status = ops.BlockedStatus(str(ex))


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
