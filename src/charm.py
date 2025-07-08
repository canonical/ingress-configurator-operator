#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service."""

import logging
import typing
from enum import Enum

import ops
from charms.haproxy.v0.haproxy_route import HaproxyRouteRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppProvider

from state.exceptions import UndefinedModeError
from state.integrator import IntegratorInformation
from state.validation import validate_config

logger = logging.getLogger(__name__)
HAPROXY_ROUTE_RELATION = "haproxy-route"
INGRESS_RELATION = "ingress"


class Mode(Enum):
    """Enum representing the mode of the charm.

    Attrs:
        INTEGRATOR: integrator mode.
        ADAPTER: afapter mode.
    """

    INTEGRATOR = "integrator"
    ADAPTER = "adapter"


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

    def detect_mode(self) -> Mode:
        """Detect the operation mode of the charm.

        Returns:
            The operation mode of the charm, either "integrator" or "adapter".

        Raises:
            UndefinedModeError: When we cannot detect the operation mode.
        """
        ingress_relation = self.model.get_relation(self._ingress.relation_name)
        if (
            self.config.get("backend_address") or self.config.get("backend_port")
        ) and ingress_relation:
            raise UndefinedModeError("Both integrator and adapter configurations are set.")
        if self.config.get("backend_address") or self.config.get("backend_port"):
            return Mode.INTEGRATOR
        if ingress_relation:
            return Mode.ADAPTER
        raise UndefinedModeError("No valid mode detected.")

    @validate_config
    def _reconcile(self, _: ops.EventBase) -> None:
        """Refresh haproxy-route requirer data."""
        mode = self.detect_mode()

        if not self._haproxy_route.relation:
            self.unit.status = ops.BlockedStatus("haproxy-route relation missing.")
            return
        if mode == Mode.INTEGRATOR:
            integrator_information = IntegratorInformation.from_charm(self)
            self._haproxy_route.provide_haproxy_route_requirements(
                service=f"{self.model.name}-{self.app.name}",
                ports=[integrator_information.backend_port],
                unit_address=str(integrator_information.backend_address),
            )
        elif mode == Mode.ADAPTER:
            relation = self.model.get_relation(self._ingress.relation_name)
            data = self._ingress.get_data(relation)
            self._haproxy_route.provide_haproxy_route_requirements(
                service=f"{data.app.model}-{data.app.name}",
                ports=[data.app.port],
                unit_address=str([udata.host for udata in data.units][0]),
            )
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(IngressConfiguratorCharm)
