# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""Any-charm with Apache HTTP server source."""

import json
import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 80
_CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm based ingress requirer serves HTTP."""

    def __init__(self, *args, **kwargs):
        """Init.

        Args:
            args: args.
            kwargs: kwargs.
        """
        super().__init__(*args, **kwargs)
        self._cfg = json.loads(_CONFIG_FILE.read_text()) if _CONFIG_FILE.exists() else {}
        port = self._cfg.get("port", _PORT)
        self.ingress = IngressPerAppRequirer(self, port=port)
        self.framework.observe(self.on.install, self._install)

    def _install(self, _: ops.InstallEvent) -> None:
        """Install apache2 and configure it using the optional config.json."""
        apt.update()
        apt.add_package(package_names="apache2")
        if self._cfg:
            port = self._cfg.get("port", _PORT)
            open_port = self._cfg.get("open_port", True)
            self._start_server(port=port, pages=self._cfg.get("pages"), open_port=open_port)

    def _start_server(
        self,
        port: int = _PORT,
        pages: dict | None = None,
        open_port: bool = True,
    ) -> None:
        """Configure apache2 to serve each path→body entry on ``port`` and open the port.

        Args:
            port: TCP port apache should listen on.
            pages: Mapping of URL path to response body.  Each path is written under
                ``/var/www/html``; parent directories are created as needed.
            open_port: When True, call ``unit.set_ports`` to advertise the port.
        """
        if pages is None:
            pages = {"/index.html": "Server Ready"}
        pathlib.Path("/etc/apache2/ports.conf").write_text(f"Listen {port}\n", encoding="utf-8")
        pathlib.Path("/etc/apache2/sites-available/000-default.conf").write_text(
            f"<VirtualHost *:{port}>\n    DocumentRoot /var/www/html\n</VirtualHost>\n",
            encoding="utf-8",
        )
        for path, body in pages.items():
            served_file = pathlib.Path("/var/www/html") / path.lstrip("/")
            served_file.parent.mkdir(parents=True, exist_ok=True)
            served_file.write_text(body, encoding="utf-8")
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        if open_port:
            self.unit.set_ports(port)
