# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""Any-charm with Apache HTTP server source."""

import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 80


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm based ingress requirer that opens its port and serves HTTP."""

    def __init__(self, *args, **kwargs):
        """Init.

        Args:
            args: args.
            kwargs: kwargs.
        """
        super().__init__(*args, **kwargs)
        self.ingress = IngressPerAppRequirer(self, port=_PORT)
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.start, self._start_apache)
        self.framework.observe(self.on.config_changed, self._start_apache)
        self.framework.observe(self.on.update_status, self._start_apache)

    def _install(self, _: ops.InstallEvent) -> None:
        """Install apache2 and pre-seed versioned API paths.

        Args:
            _: The triggering Juju event.
        """
        apt.update()
        apt.add_package(package_names="apache2")
        base = pathlib.Path("/var/www/html/api")
        for version in ("v1", "v2"):
            (base / version).mkdir(parents=True, exist_ok=True)
            (base / version / "index.html").write_text(f"{version} ok!", encoding="utf-8")

    def _start_apache(self, _: ops.EventBase) -> None:
        """Start apache2 and open the port on lifecycle events.

        Args:
            _: The triggering Juju event.
        """
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.set_ports(_PORT)

    def start_server(
        self,
        port: int = _PORT,
        path: str = "/index.html",
        body: str = "Server Ready",
    ) -> None:
        """Configure apache2 to serve ``body`` at ``path`` on ``port`` and open the port."""
        pathlib.Path("/etc/apache2/ports.conf").write_text(f"Listen {port}\n", encoding="utf-8")
        pathlib.Path("/etc/apache2/sites-available/000-default.conf").write_text(
            f"<VirtualHost *:{port}>\n    DocumentRoot /var/www/html\n</VirtualHost>\n",
            encoding="utf-8",
        )
        served_file = pathlib.Path("/var/www/html") / path.lstrip("/")
        served_file.parent.mkdir(parents=True, exist_ok=True)
        served_file.write_text(body, encoding="utf-8")
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.set_ports(port)
