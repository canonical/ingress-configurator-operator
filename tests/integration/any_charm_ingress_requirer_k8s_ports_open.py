# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error

"""Kubernetes ingress requirer that opens its workload port (``is_port_open=True``).

This any-charm-k8s source backs tests that need an open-ports ingress requirer. It:
  * declares the ingress requirement on a fixed port,
  * runs a catch-all HTTP server (perl, which ships in the workload image) on that port via a
    Pebble layer in the workload container, and
  * opens the port with ``open-port`` so the ``ingress`` databag reports ``is_port_open=True``.

The catch-all server returns 200 for every path, mirroring the flask-k8s closed-ports backend,
so path-restriction behaviour is identical regardless of which backend a test uses.
"""

import ops
from any_charm_base import AnyCharmBase  # type: ignore
from ingress import IngressPerAppRequirer  # type: ignore

_PORT = 8000
_WORKLOAD_CONTAINER = "any"

# Minimal catch-all HTTP/1.1 server using only perl core modules (no extra packages needed).
_SERVER = r"""use IO::Socket::INET;
$| = 1;
my $port = $ENV{PORT} || 8000;
my $srv = IO::Socket::INET->new(
    LocalAddr => "0.0.0.0", LocalPort => $port,
    Listen => 10, Reuse => 1, Proto => "tcp",
) or die "bind: $!";
while (my $cli = $srv->accept) {
    while (my $line = <$cli>) { last if $line =~ /^\r?\n$/; }
    my $body = "ok from open-ports backend";
    print $cli "HTTP/1.1 200 OK\r\n"
        . "Content-Type: text/plain\r\n"
        . "Content-Length: " . length($body) . "\r\n"
        . "Connection: close\r\n\r\n"
        . $body;
    close $cli;
}
"""


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
        self.framework.observe(self.on[_WORKLOAD_CONTAINER].pebble_ready, self._configure)

    def _configure(self, event: ops.PebbleReadyEvent) -> None:
        """Push the server, start it via Pebble, and open the workload port.

        Args:
            event: The pebble-ready event for the workload container.
        """
        container = event.workload
        container.push("/server.pl", _SERVER, make_dirs=True)
        container.add_layer(
            "http-server",
            {
                "summary": "catch-all http server",
                "description": "Serves 200 on every path for ingress tests.",
                "services": {
                    "http": {
                        "override": "replace",
                        "command": "perl /server.pl",
                        "startup": "enabled",
                        "environment": {"PORT": str(_PORT)},
                    }
                },
            },
            combine=True,
        )
        container.replan()
        self.unit.open_port("tcp", _PORT)
        self.unit.status = ops.ActiveStatus()
