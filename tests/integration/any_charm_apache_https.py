# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess to install apache2 and configure TLS.
# No external inputs are parsed, ignoring bandit errors with nosec

"""Any-charm with Apache HTTPS server source (self-signed certificate).

The charm generates a local CA and a server certificate signed by that CA.
The CA certificate is published to any ``send-ca-cert`` relations so that
content-cache can verify the backend via ``proxy_ssl_verify on``.
"""

import json
import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from charmlibs import apt  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 443
_CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"
_CA_KEY_PATH = pathlib.Path("/etc/ssl/private/apache-ca.key")
_CA_CERT_PATH = pathlib.Path("/etc/ssl/certs/apache-ca.crt")
_SERVER_KEY_PATH = pathlib.Path("/etc/ssl/private/apache-server.key")
_SERVER_CERT_PATH = pathlib.Path("/etc/ssl/certs/apache-server.crt")
_SERVER_CSR_PATH = pathlib.Path("/tmp/apache-server.csr")  # nosec: B108


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm based ingress requirer that serves HTTPS with a CA-signed certificate."""

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
        self.framework.observe(
            self.on.send_ca_cert_relation_joined, self._on_send_ca_cert_relation_joined
        )

    def _on_send_ca_cert_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish the CA certificate to the new send-ca-cert relation.

        Args:
            event: The relation joined event.
        """
        self._publish_ca_cert(event.relation)

    def _publish_ca_cert(self, relation: ops.Relation) -> None:
        """Write the CA certificate to a send-ca-cert relation databag.

        Uses the V0 format (unit databag ``ca`` key) understood by content-cache.

        Args:
            relation: The send-ca-cert relation to write to.
        """
        if not _CA_CERT_PATH.exists():
            return
        ca_pem = _CA_CERT_PATH.read_text(encoding="utf-8")
        relation.data[self.unit]["ca"] = ca_pem

    def _install(self, _: ops.InstallEvent) -> None:
        """Install apache2 with mod_ssl and configure it with a CA-signed certificate."""
        apt.update()
        apt.add_package(package_names="apache2")
        apt.add_package(package_names="openssl")
        port = self._cfg.get("port", _PORT)
        pages = self._cfg.get("pages")
        self._start_server(port=port, pages=pages)
        # Publish CA cert to any relations that were already joined.
        for relation in self.model.relations.get("send-ca-cert", []):
            self._publish_ca_cert(relation)

    def _start_server(
        self,
        port: int = _PORT,
        pages: dict | None = None,
    ) -> None:
        """Configure apache2 to serve HTTPS on ``port`` with a CA-signed certificate.

        Generates a local CA key + cert, then signs a server certificate with it.
        This allows content-cache to verify the backend via ``proxy_ssl_verify on``
        by trusting the CA cert published to the ``send-ca-cert`` relation.

        Args:
            port: TCP port apache should listen on (default 443).
            pages: Mapping of URL path to response body.
        """
        if pages is None:
            pages = {"/index.html": "Server Ready"}

        # Generate CA key.
        subprocess.run(  # nosec: B603, B607
            ["openssl", "genrsa", "-out", str(_CA_KEY_PATH), "2048"],
            check=True,
        )
        # Generate self-signed CA certificate.
        subprocess.run(  # nosec: B603, B607
            [
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(_CA_KEY_PATH),
                "-sha256",
                "-days",
                "365",
                "-out",
                str(_CA_CERT_PATH),
                "-subj",
                "/CN=Test CA",
            ],
            check=True,
        )
        # Generate server key.
        subprocess.run(  # nosec: B603, B607
            ["openssl", "genrsa", "-out", str(_SERVER_KEY_PATH), "2048"],
            check=True,
        )
        # Generate server CSR.
        subprocess.run(  # nosec: B603, B607
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(_SERVER_KEY_PATH),
                "-out",
                str(_SERVER_CSR_PATH),
                "-subj",
                "/CN=localhost",
            ],
            check=True,
        )
        # Sign server cert with CA.
        subprocess.run(  # nosec: B603, B607
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(_SERVER_CSR_PATH),
                "-CA",
                str(_CA_CERT_PATH),
                "-CAkey",
                str(_CA_KEY_PATH),
                "-CAcreateserial",
                "-out",
                str(_SERVER_CERT_PATH),
                "-days",
                "365",
                "-sha256",
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
            f"    SSLCertificateFile {_SERVER_CERT_PATH}\n"
            f"    SSLCertificateKeyFile {_SERVER_KEY_PATH}\n"
            "</VirtualHost>\n",
            encoding="utf-8",
        )
        # Disable default HTTP site to avoid port conflicts.
        subprocess.run(["a2dissite", "000-default"], check=False)  # nosec: B603, B607
        subprocess.run(["a2ensite", "000-default-ssl"], check=True)  # nosec: B603, B607
        subprocess.run(["service", "apache2", "restart"], check=False)  # nosec: B603, B607
        self.unit.set_ports(port)
