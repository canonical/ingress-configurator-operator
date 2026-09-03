# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=duplicate-code,import-error
# We use subprocess to manage a systemd service; no external inputs are parsed,
# so bandit subprocess warnings are suppressed with nosec.

"""Any-charm HTTPS backend served by a simple Python ``http.server``.

The CA and the server certificate (valid for the backend hostname via a SAN) are generated
by the test and passed in through ``config.json``.  content-cache verifies the backend TLS
connection with ``proxy_ssl_verify on`` + ``proxy_ssl_name <backend_hostname>``, so:

* the served certificate carries a ``DNS:<backend_hostname>`` SAN, and
* the CA is published to ``provide-certificate-transfer`` so content-cache trusts it.

Unlike an Apache backend, a plain Python TLS server ignores the SNI in the incoming
connection (it always presents the single configured certificate), which is exactly the
behaviour we want for a backend that must not do SNI-based routing.  The certificate is
IP-independent, so every unit of the application can serve the identical certificate,
letting the test exercise multiple backend units behind content-cache.
"""

import json
import pathlib
import subprocess  # nosec: B404

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 443
_CONFIG_FILE = pathlib.Path(__file__).parent / "config.json"
_DOCROOT = pathlib.Path("/var/www/html")
_SERVER_SCRIPT = pathlib.Path("/opt/https_server.py")
_SERVER_CERT_PATH = pathlib.Path("/etc/ssl/certs/backend-server.crt")
_SERVER_KEY_PATH = pathlib.Path("/etc/ssl/private/backend-server.key")
_CA_CERT_PATH = pathlib.Path("/etc/ssl/certs/backend-ca.crt")
_SERVICE_NAME = "https-backend.service"
_SERVICE_PATH = pathlib.Path("/etc/systemd/system") / _SERVICE_NAME

# Minimal HTTPS file server: serves files from a directory and presents a fixed certificate
# regardless of the client's SNI.  Arguments: <directory> <port> <certfile> <keyfile>.
_SERVER_SCRIPT_BODY = '''\
"""Minimal HTTPS file server that ignores SNI and serves a fixed certificate."""
import functools
import http.server
import ssl
import sys

directory, port, certfile, keyfile = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile, keyfile)
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
httpd.serve_forever()
'''


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Any-charm ingress requirer that serves HTTPS from a simple Python server."""

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
        # Observe relation_created (and relation_changed) rather than relation_joined:
        # Juju only fires relation_joined on the provider side after the requirer unit
        # completes its own relation_joined hook, which in practice may never happen in
        # this test setup. relation_created always fires when the relation is created, and
        # relation_changed fires reliably too, so together they guarantee the CA cert is
        # published to content-cache (otherwise its CA bundle lacks the backend CA and
        # nginx proxy_ssl_verify fails with 502).
        self.framework.observe(
            self.on["provide-certificate-transfer"].relation_created,
            self._on_provide_certificate_transfer_relation_event,
        )
        self.framework.observe(
            self.on["provide-certificate-transfer"].relation_changed,
            self._on_provide_certificate_transfer_relation_event,
        )

    def _on_provide_certificate_transfer_relation_event(self, event: ops.RelationEvent) -> None:
        """Publish the CA certificate to the certificate-transfer relation.

        Args:
            event: The relation event (created or changed).
        """
        self._publish_ca_cert(event.relation)

    def _publish_ca_cert(self, relation: ops.Relation) -> None:
        """Write the CA certificate to a certificate-transfer relation databag (V0 format).

        Args:
            relation: The certificate-transfer relation to write to.
        """
        if not _CA_CERT_PATH.exists():
            return
        relation.data[self.unit]["ca"] = _CA_CERT_PATH.read_text(encoding="utf-8")
        # V0 certificate-transfer format: content-cache reads "chain" first (JSON list),
        # then falls back to "ca". An empty chain keeps it on the "ca" field.
        relation.data[self.unit]["chain"] = "[]"

    def _install(self, _: ops.InstallEvent) -> None:
        """Provision the certificate, write pages, and start the HTTPS server."""
        port = self._cfg.get("port", _PORT)
        pages = self._cfg.get("pages") or {"/index.html": "Server Ready"}
        self._write_certificates()
        self._write_pages(pages)
        self._start_server(port)
        # Publish CA cert to any relations that were already joined.
        for relation in self.model.relations.get("provide-certificate-transfer", []):
            self._publish_ca_cert(relation)
        self.unit.set_ports(port)

    def _write_certificates(self) -> None:
        """Write the CA and server certificate/key supplied via config.json to disk."""
        _SERVER_CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SERVER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SERVER_CERT_PATH.write_text(self._cfg["server_cert"], encoding="utf-8")
        _SERVER_KEY_PATH.write_text(self._cfg["server_key"], encoding="utf-8")
        _CA_CERT_PATH.write_text(self._cfg["ca_cert"], encoding="utf-8")

    def _write_pages(self, pages: dict) -> None:
        """Write each path→body entry under the document root.

        Args:
            pages: Mapping of URL path to response body.
        """
        for path, body in pages.items():
            served_file = _DOCROOT / path.lstrip("/")
            served_file.parent.mkdir(parents=True, exist_ok=True)
            served_file.write_text(body, encoding="utf-8")

    def _start_server(self, port: int) -> None:
        """Install and start a systemd service running the Python HTTPS server.

        Args:
            port: TCP port to serve HTTPS on.
        """
        _SERVER_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
        _SERVER_SCRIPT.write_text(_SERVER_SCRIPT_BODY, encoding="utf-8")
        exec_start = (
            f"/usr/bin/python3 {_SERVER_SCRIPT} {_DOCROOT} {port} "
            f"{_SERVER_CERT_PATH} {_SERVER_KEY_PATH}"
        )
        _SERVICE_PATH.write_text(
            "[Unit]\n"
            "Description=Test HTTPS backend\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"ExecStart={exec_start}\n"
            "Restart=always\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n",
            encoding="utf-8",
        )
        subprocess.run(["systemctl", "daemon-reload"], check=True)  # nosec: B603, B607
        subprocess.run(  # nosec: B603, B607
            ["systemctl", "enable", "--now", _SERVICE_NAME], check=True
        )
