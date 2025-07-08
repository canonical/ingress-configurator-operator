# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for integration tests."""

import ipaddress
import subprocess
from urllib.parse import urlparse

from requests import Session
from requests.adapters import DEFAULT_POOLBLOCK, DEFAULT_POOLSIZE, DEFAULT_RETRIES, HTTPAdapter

from .conftest import MOCK_HAPROXY_HOSTNAME


class DNSResolverHTTPSAdapter(HTTPAdapter):
    """A simple mounted DNS resolver for HTTP requests."""

    def __init__(
        self,
        hostname,
        ip,
    ):
        """Initialize the dns resolver.

        Args:
            hostname: DNS entry to resolve.
            ip: Target IP address.
        """
        self.hostname = hostname
        self.ip = ip
        super().__init__(
            pool_connections=DEFAULT_POOLSIZE,
            pool_maxsize=DEFAULT_POOLSIZE,
            max_retries=DEFAULT_RETRIES,
            pool_block=DEFAULT_POOLBLOCK,
        )

    # Ignore pylint rule as this is the parent method signature
    def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ):  # pylint: disable=too-many-arguments, too-many-positional-arguments
        """Wrap HTTPAdapter send to modify the outbound request.

        Args:
            request: Outbound HTTP request.
            stream: argument used by parent method.
            timeout: argument used by parent method.
            verify: argument used by parent method.
            cert: argument used by parent method.
            proxies: argument used by parent method.

        Returns:
            Response: HTTP response after modification.
        """
        connection_pool_kwargs = self.poolmanager.connection_pool_kw

        result = urlparse(request.url)
        if result.hostname == self.hostname:
            ip = self.ip
            if result.scheme == "https" and ip:
                request.url = request.url.replace(
                    "https://" + result.hostname,
                    "https://" + ip,
                )
                connection_pool_kwargs["server_hostname"] = result.hostname
                connection_pool_kwargs["assert_hostname"] = result.hostname
                request.headers["Host"] = result.hostname
            else:
                connection_pool_kwargs.pop("server_hostname", None)
                connection_pool_kwargs.pop("assert_hostname", None)

        return super().send(request, stream, timeout, verify, cert, proxies)


def haproxy_request(public_address: str):
    """Make a request to the HAPRoxy server.

    Args:
        public_address: the IP address of HAProxy.

    Returns: the response for the request.
    """
    haproxy_address = ipaddress.ip_address(public_address)
    session = Session()
    session.mount(
        "https://",
        DNSResolverHTTPSAdapter(MOCK_HAPROXY_HOSTNAME, str(haproxy_address)),
    )
    response = session.get(
        f"https://{MOCK_HAPROXY_HOSTNAME}",
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
    return response


def start_http_server():
    """Start apache2 webserver."""
    update = ["apt-get", "update", "--error-on=any"]
    subprocess.run(update, capture_output=True, check=True)  # nosec
    install = [
        "apt-get",
        "install",
        "-y",
        "--option=Dpkg::Options::=--force-confold",
        "apache2",
    ]
    subprocess.run(install, capture_output=True, check=True)  # nosec
