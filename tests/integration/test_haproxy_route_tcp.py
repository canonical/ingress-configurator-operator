# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the ingress per unit relation."""
import logging
import socket
import ssl
import time

import jubilant
import pytest

from .conftest import get_unit_addresses

logger = logging.getLogger(__name__)

@pytest.mark.abort_on_fail
def test_haproxy_route_tcp(
    application_with_tcp_server: str,
    haproxy: str,
    juju: jubilant.Juju,
):
    """Deploy the charm with anycharm ingress per unit requirer that installs apache2.

    Assert that the requirer endpoints are available.
    """
    juju.integrate(
        f"{haproxy}:haproxy-route-tcp",
        application_with_tcp_server,
    )
    application_ip_address = get_unit_addresses(juju, application_with_tcp_server)[0]
    juju.config(
        application_with_tcp_server,
        {
            "tcp-frontend-port": 4444,
            "tcp-backend-port": 4000,
            "tcp-hostname": "example.com",
            "tcp-tls-terminate": True,
            "tcp-backend-addresses": str(application_ip_address),
        },
    )

    juju.wait(lambda status: jubilant.all_active(status, haproxy, application_with_tcp_server))
    haproxy_ip_address = get_unit_addresses(juju, haproxy)[0]
    context = ssl._create_unverified_context()  # pylint: disable=protected-access  # nosec
    deadline = time.time() + 30
    address = (str(haproxy_ip_address), 4444)
    while time.time() < deadline:
        try:
            with (
                socket.create_connection(address) as sock,
                context.wrap_socket(sock, server_hostname="example.com") as ssock,
            ):
                ssock.send(b"ping")
                server_response = ssock.read()
                assert "pong" in str(server_response)
                return
        except ConnectionRefusedError:
            logger.info(f"connection to %s refused, retrying", address)
            time.sleep(1)
    raise TimeoutError("timed out waiting for server to respond")
