# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the ingress per unit relation."""

import socket
import ssl

import jubilant
import pytest

from .conftest import get_unit_addresses


@pytest.mark.abort_on_fail
async def test_haproxy_route_tcp(
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
            "tcp-backend-addresses": str(application_ip_address),
        },
    )

    juju.wait(lambda status: jubilant.all_active(status, haproxy, application_with_tcp_server))
    haproxy_ip_address = get_unit_addresses(juju, haproxy)[0]
    # We need to call _create_unverified_context() to test with self-signed certs
    context = ssl._create_unverified_context()  # pylint: disable=protected-access  # nosec
    with (
        socket.create_connection((str(haproxy_ip_address), 4444)) as sock,
        context.wrap_socket(sock, server_hostname="example.com") as ssock,
    ):
        ssock.send(b"ping")
        server_response = ssock.read()
        assert "pong" in str(server_response)
