# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""Ingress requirer source."""

import subprocess  # nosec

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from ingress import IngressPerAppRequirer


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Ingress requirer charm src."""

    def __init__(self, *args, **kwargs):
        """Init.

        Args:
            args: args.
            kwargs: kwargs.
        """
        super().__init__(*args, **kwargs)
        self.ingress = IngressPerAppRequirer(self, port=80)
        self.unit.status = ops.BlockedStatus("Waiting for ingress relation")
        self.framework.observe(self.on.ingress_relation_changed, self._on_ingress_relation_changed)

    def start_server(self):
        """Start apache2 webserver."""
        update = ["apt-get", "update", "--error-on=any"]
        subprocess.run(update, capture_output=True, check=True)  # nosec
        install = [
            "apt-get",
            "install",
            "-y",
            "--option=Dpkg::Options::=--force-confold",
            "apache2",
        ]
        subprocess.run(install, capture_output=True, check=True)  # nosec

    def _on_ingress_relation_changed(self, _: ops.ConfigChangedEvent):
        """Relation changed handler."""
        self.unit.status = ops.ActiveStatus()
