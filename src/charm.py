#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import logging
import typing

import ops
from charms.haproxy.v0.haproxy_route import HaproxyRouteRequirer

from state.integrator import IntegratorInformation
from state.validation import validate_config

logger = logging.getLogger(__name__)
HAPROXY_ROUTE_RELATION = "haproxy-route"


class IngressConfiguratorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Initialize the ingress-configurator charm.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self._haproxy_route = HaproxyRouteRequirer(self, HAPROXY_ROUTE_RELATION)
        self.framework.observe(self.on.config_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_changed, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_broken, self._reconcile)
        self.framework.observe(self.on[HAPROXY_ROUTE_RELATION].relation_departed, self._reconcile)

    @validate_config
    def _reconcile(self, _: ops.EventBase) -> None:
        """Refresh haproxy-route requirer data."""
        integrator_information = IntegratorInformation.from_charm(self)
        if not self._haproxy_route.relation:
            self.unit.status = ops.BlockedStatus("haproxy-route relation missing.")
            return
        self._haproxy_route.provide_haproxy_route_requirements(
            service=f"{self.model.name}-{self.app.name}",
            ports=[integrator_information.backend_port],
            paths=integrator_information.paths,
            subdomains=integrator_information.subdomains,
            unit_address=str(integrator_information.backend_address),
        )
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
