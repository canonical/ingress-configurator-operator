# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for integration tests."""

import re
from urllib.parse import urlparse

import jubilant
import requests
import urllib3
from requests.adapters import DEFAULT_POOLBLOCK, DEFAULT_POOLSIZE, DEFAULT_RETRIES, HTTPAdapter
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_IPV4_RE = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")


def get_gateway_address(juju: jubilant.Juju, gateway_api_integrator: str) -> str:
    """Extract the gateway LoadBalancer address from the integrator's status message.

    The gateway-api-integrator charm surfaces its assigned address in the application status
    message, e.g. ``Gateway addresses: 10.0.0.10 (enforce-https is set to false)``.

    Args:
        juju: Jubilant Juju instance for the model.
        gateway_api_integrator: The gateway-api-integrator application name.

    Returns:
        The first IPv4 address found in the status message, or an empty string.
    """
    status = juju.status()
    message = status.apps[gateway_api_integrator].app_status.message
    match = _IPV4_RE.search(message)
    return match.group(1) if match else ""


@retry(
    stop=stop_after_delay(180),
    wait=wait_fixed(5),
    retry=retry_if_exception_type((AssertionError, requests.exceptions.RequestException)),
    reraise=True,
)
def wait_for_gateway_response(
    gateway_address: str,
    hostname: str | None,
    path: str,
    *,
    scheme: str = "http",
    expected_status: int = 200,
    body_contains: str | None = None,
    allow_redirects: bool = True,
) -> requests.Response:
    """Wait until the gateway returns a response matching the expectations and return it.

    Args:
        gateway_address: The gateway LoadBalancer IP to send the request to.
        hostname: Value for the ``Host`` header; ``None`` sends no Host header.
        path: Request path (including leading slash).
        scheme: ``http`` or ``https``.
        expected_status: Expected HTTP status code.
        body_contains: Optional substring expected in the response body.
        allow_redirects: Whether to follow redirects; set ``False`` to assert a redirect status.

    Returns:
        The successful :class:`requests.Response`.

    Raises:
        AssertionError: If the expected response is not observed within 180 seconds.
        requests.exceptions.RequestException: If the request keeps failing within 180 seconds.
    """
    session = requests.Session()
    if hostname is not None:
        # Resolve the hostname to the gateway IP so the Host header and TLS SNI carry it,
        # which hostname-scoped gateway listeners require to route correctly.
        session.mount(f"{scheme}://{hostname}", DNSResolverAdapter(hostname, gateway_address))
        url = f"{scheme}://{hostname}{path}"
    else:
        url = f"{scheme}://{gateway_address}{path}"

    response = session.get(
        url,
        verify=False,  # nosec - testing against a self-signed / IP-addressed endpoint
        allow_redirects=allow_redirects,
        timeout=10,
    )
    assert response.status_code == expected_status, (
        f"Unexpected status routing Host={hostname} {path}: "
        f"got {response.status_code}, expected {expected_status}, body={response.text!r}"
    )
    if body_contains is not None:
        assert body_contains in response.text, (
            f"Expected body for Host={hostname} {path} to contain {body_contains!r}, "
            f"body={response.text!r}"
        )
    return response


class DNSResolverAdapter(HTTPAdapter):
    """A simple mounted DNS resolver for HTTP requests, with retry support."""

    def __init__(
        self,
        hostname,
        ip,
    ):
        """Initialize the DNS resolver with retry configuration.

        Args:
            hostname: DNS entry to resolve.
            ip: Target IP address.
        """
        self.hostname = hostname
        self.ip = ip

        super().__init__(
            max_retries=DEFAULT_RETRIES,
            pool_connections=DEFAULT_POOLSIZE,
            pool_maxsize=DEFAULT_POOLSIZE,
            pool_block=DEFAULT_POOLBLOCK,
        )

    # Ignore pylint rule as this is the parent method signature
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):  # pylint: disable=too-many-arguments, too-many-positional-arguments
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
            if result.scheme == "http" and ip:
                request.url = request.url.replace(
                    "http://" + result.hostname,
                    "http://" + ip,
                )
                connection_pool_kwargs["server_hostname"] = result.hostname
                request.headers["Host"] = result.hostname
            elif result.scheme == "https" and ip:
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
