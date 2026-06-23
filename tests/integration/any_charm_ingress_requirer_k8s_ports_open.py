# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error

"""Kubernetes ingress requirer that opens its workload port (``is_port_open=True``).

This any-charm-k8s source backs tests that need an open-ports ingress requirer. Mirroring the
gateway-api-integrator e2e ingress requirer, it installs apache2 in the charm container (which
shares the pod network namespace with the workload, so a server bound there is reachable on the
pod IP) and runs it as a managed service. It:
  * declares the ingress requirement on a fixed port,
  * serves a catch-all HTTP response (200 on every path) on that port, and
  * opens the port with ``open-port`` so the ``ingress`` databag reports ``is_port_open=True``.

The catch-all behaviour mirrors the flask-k8s closed-ports backend, so the path restriction
enforced upstream by the gateway is what gets tested regardless of which backend a test uses.
"""

import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 8000


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm-k8s based ingress requirer that opens its port and serves HTTP."""

    def __init__(self, *args, **kwargs):
        """Init.

        Args:
            args: args.
            kwargs: kwargs.
        """
        super().__init__(*args, **kwargs)
        self.ingress = IngressPerAppRequirer(self, port=_PORT)
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.start, self._configure)
        self.framework.observe(self.on.config_changed, self._configure)
        self.framework.observe(self.on.update_status, self._configure)

    def _install(self, _: ops.InstallEvent) -> None:
        """Install and configure apache2 as a catch-all backend on the ingress port.

        Args:
            _: The triggering Juju event.
        """
        apt.update()
        apt.add_package(package_names="apache2")
        # Listen on the ingress port and return 200 for every path (FallbackResource), so the
        # path restriction enforced upstream by the gateway is what the test exercises.
        pathlib.Path("/etc/apache2/ports.conf").write_text(f"Listen {_PORT}\n", encoding="utf-8")
        pathlib.Path("/etc/apache2/sites-available/000-default.conf").write_text(
            f"<VirtualHost *:{_PORT}>\n"
            "    DocumentRoot /var/www/html\n"
            "    FallbackResource /index.html\n"
            "</VirtualHost>\n",
            encoding="utf-8",
        )
        pathlib.Path("/var/www/html/index.html").write_text(
            "ok from open-ports backend", encoding="utf-8"
        )

    def _configure(self, _: ops.EventBase) -> None:
        """Start apache2 and open the workload port.

        Args:
            _: The triggering Juju event.
        """
        # Restart (not start) so the listen-port change applied in _install is always picked up.
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.open_port("tcp", _PORT)
        self.unit.status = ops.ActiveStatus()
