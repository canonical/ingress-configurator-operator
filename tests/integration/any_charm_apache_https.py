# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess to install apache2 and configure TLS.
# No external inputs are parsed, ignoring bandit errors with nosec

"""Any-charm with Apache HTTPS server source (self-signed certificate)."""

import json
import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 443
_CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"
_CERT_PATH = pathlib.Path("/etc/ssl/certs/apache-selfsigned.crt")
_KEY_PATH = pathlib.Path("/etc/ssl/private/apache-selfsigned.key")


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm based ingress requirer that serves HTTPS with a self-signed certificate."""

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
        """Install apache2 with mod_ssl and configure it with a self-signed certificate."""
        apt.update()
        apt.add_package(package_names="apache2")
        apt.add_package(package_names="openssl")
        port = self._cfg.get("port", _PORT)
        pages = self._cfg.get("pages")
        self._start_server(port=port, pages=pages)

    def _start_server(
        self,
        port: int = _PORT,
        pages: dict | None = None,
    ) -> None:
        """Configure apache2 to serve HTTPS on ``port`` with a self-signed certificate.

        Args:
            port: TCP port apache should listen on (default 443).
            pages: Mapping of URL path to response body.
        """
        if pages is None:
            pages = {"/index.html": "Server Ready"}

        # Generate a self-signed certificate valid for 365 days.
        subprocess.run(  # nosec: B603, B607
            [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-days",
                "365",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(_KEY_PATH),
                "-out",
                str(_CERT_PATH),
                "-subj",
                "/CN=localhost",
            ],
            check=True,
        )

        # Enable SSL module.
        subprocess.run(["a2enmod", "ssl"], check=True)  # nosec: B603, B607

        # Write pages to DocumentRoot.
        for path, body in pages.items():
            served_file = pathlib.Path("/var/www/html") / path.lstrip("/")
            served_file.parent.mkdir(parents=True, exist_ok=True)
            served_file.write_text(body, encoding="utf-8")

        # Configure the HTTPS virtual host.
        pathlib.Path("/etc/apache2/ports.conf").write_text(f"Listen {port}\n", encoding="utf-8")
        pathlib.Path("/etc/apache2/sites-available/000-default-ssl.conf").write_text(
            f"<VirtualHost *:{port}>\n"
            "    DocumentRoot /var/www/html\n"
            "    SSLEngine on\n"
            f"    SSLCertificateFile {_CERT_PATH}\n"
            f"    SSLCertificateKeyFile {_KEY_PATH}\n"
            "</VirtualHost>\n",
            encoding="utf-8",
        )
        # Disable default HTTP site to avoid port conflicts.
        subprocess.run(["a2dissite", "000-default"], check=False)  # nosec: B603, B607
        subprocess.run(["a2ensite", "000-default-ssl"], check=True)  # nosec: B603, B607
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.set_ports(port)
