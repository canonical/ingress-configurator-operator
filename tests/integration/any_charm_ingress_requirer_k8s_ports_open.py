# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error

"""Kubernetes ingress requirer that opens its workload port (``is_port_open=True``).

This any-charm-k8s source backs tests that need an open-ports ingress requirer. It:
  * declares the ingress requirement on a fixed port,
  * runs a catch-all HTTP server (python3 from the charm container, which shares the pod
    network namespace with the workload so the bound port is reachable on the pod IP) on that
    port, and
  * opens the port with ``open-port`` so the ``ingress`` databag reports ``is_port_open=True``.

The catch-all server returns 200 for every path, mirroring the flask-k8s closed-ports backend,
so path-restriction behaviour is identical regardless of which backend a test uses.
"""

import socket
import subprocess  # nosec: B404
import sys
import textwrap

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 8000

# Minimal catch-all HTTP server using only the Python standard library; returns 200 on every path.
_SERVER = textwrap.dedent(
    f"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = b"ok from open-ports backend"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(("0.0.0.0", {_PORT}), Handler).serve_forever()
    """
)


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
        self.framework.observe(self.on.start, self._configure)
        self.framework.observe(self.on.config_changed, self._configure)
        self.framework.observe(self.on.update_status, self._configure)

    def _configure(self, _: ops.EventBase) -> None:
        """Ensure the catch-all server is running and open the workload port.

        Args:
            _: The triggering Juju event.
        """
        self._ensure_server_running()
        self.unit.open_port("tcp", _PORT)
        self.unit.status = ops.ActiveStatus()

    def _ensure_server_running(self) -> None:
        """Spawn the python catch-all HTTP server if it is not already listening."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", _PORT)) == 0:
                return
        # Detach so the server outlives the charm hook. Safe: fixed argument list, no shell,
        # no user input.
        subprocess.Popen(  # nosec: B603
            [sys.executable, "-c", _SERVER],
            start_new_session=True,
        )
