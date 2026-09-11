# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""Any-charm ingress-per-unit requirer that serves its own unit name over HTTP."""

import json
import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress_per_unit import IngressPerUnitRequirer  # type: ignore

_PORT = 8080
_CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm based ingress-per-unit requirer serving HTTP."""

    def __init__(self, *args, **kwargs):
        """Init.

        Args:
            args: args.
            kwargs: kwargs.
        """
        super().__init__(*args, **kwargs)
        self._cfg = json.loads(_CONFIG_FILE.read_text()) if _CONFIG_FILE.exists() else {}
        port = self._cfg.get("port", _PORT)
        self.ingress_per_unit = IngressPerUnitRequirer(
            self,
            port=port,
            relation_name="require-ingress-per-unit",
            strip_prefix=True,
        )
        self.framework.observe(self.on.install, self._install)

    def _install(self, _: ops.InstallEvent) -> None:
        """Install apache2 and serve this unit's name at the document root."""
        apt.update()
        apt.add_package(package_names="apache2")
        self._start_server(port=self._cfg.get("port", _PORT))

    def _start_server(self, port: int = _PORT) -> None:
        """Configure apache2 to serve this unit's name on ``port`` and open the port.

        Serving ``self.unit.name`` lets the test assert that each per-unit URL routes to
        the correct requirer unit (strip_prefix rewrites the matched prefix to ``/``).

        Args:
            port: TCP port apache should listen on.
        """
        pathlib.Path("/etc/apache2/ports.conf").write_text(f"Listen {port}\n", encoding="utf-8")
        pathlib.Path("/etc/apache2/sites-available/000-default.conf").write_text(
            f"<VirtualHost *:{port}>\n    DocumentRoot /var/www/html\n</VirtualHost>\n",
            encoding="utf-8",
        )
        pathlib.Path("/var/www/html/index.html").write_text(self.unit.name, encoding="utf-8")
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.set_ports(port)
