# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the ingress per unit relation."""

import logging
import socket
import ssl
import time

import jubilant
import pytest

from .conftest import (
    APP_NAME,
    HAPROXY_APP_NAME,
    deploy_with_haproxy,
    get_unit_addresses,
    setup_tcp_server,
)

logger = logging.getLogger(__name__)


@pytest.mark.juju_setup
def test_deploy_with_haproxy(juju: jubilant.Juju, charm: str):
    deploy_with_haproxy(juju, charm)


@pytest.mark.juju_setup
def test_setup_tcp_server(juju: jubilant.Juju):
    setup_tcp_server(juju)


def test_haproxy_route_tcp(juju: jubilant.Juju):
    """Deploy the charm with anycharm ingress per unit requirer that installs apache2.

    Assert that the requirer endpoints are available.
    """
    juju.integrate(
        f"{HAPROXY_APP_NAME}:haproxy-route-tcp",
        APP_NAME,
    )
    application_ip_address = get_unit_addresses(juju, APP_NAME)[0]
    juju.config(
        APP_NAME,
        {
            "tcp-frontend-port": 4444,
            "tcp-backend-port": 4000,
            "tcp-hostname": "example.com",
            "tcp-tls-terminate": True,
            "tcp-backend-addresses": str(application_ip_address),
        },
    )

    juju.wait(lambda status: jubilant.all_active(status, HAPROXY_APP_NAME, APP_NAME), delay=5)
    haproxy_ip_address = get_unit_addresses(juju, HAPROXY_APP_NAME)[0]
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
            logger.info("connection to %s refused, retrying", address)
            time.sleep(1)
    raise TimeoutError("timed out waiting for server to respond")
