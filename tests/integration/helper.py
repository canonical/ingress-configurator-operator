# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for integration tests."""

import re
from urllib.parse import urlparse

import jubilant
import requests
import urllib3
from lightkube import Client
from lightkube.resources.core_v1 import Service
from lightkube.resources.discovery_v1 import EndpointSlice
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


def assert_gateway_response(
    gateway_address: str,
    hostname: str | None,
    path: str,
    *,
    scheme: str = "http",
    expected_status: int = 200,
    body_contains: str | None = None,
    allow_redirects: bool = True,
    resolve_hostname: bool = False,
    timeout: int = 180,
) -> requests.Response:
    """Request a path through the gateway and assert the response, retrying until convergence.

    The dataplane (Gateway, HTTPRoute, EndpointSlice) can take a few seconds to converge after a
    config or relation change, so this retries on connection errors and assertion failures until
    ``timeout`` is reached.

    Args:
        gateway_address: The gateway LoadBalancer IP to send the request to.
        hostname: Value for the ``Host`` header; ``None`` sends no Host header.
        path: Request path (including leading slash).
        scheme: ``http`` or ``https``.
        expected_status: Expected HTTP status code.
        body_contains: Optional substring expected in the response body.
        allow_redirects: Whether to follow redirects; set ``False`` to assert a redirect status.
        resolve_hostname: When True, send the request to ``hostname`` and resolve it to
            ``gateway_address`` so the TLS SNI matches the hostname (required for HTTPS routing
            on hostname-scoped gateway listeners).
        timeout: Maximum seconds to keep retrying.

    Returns:
        The successful :class:`requests.Response`.

    Raises:
        AssertionError: If the expected response is not observed within ``timeout``.
        requests.exceptions.RequestException: If the request keeps failing within ``timeout``.
    """
    headers = {"Host": hostname} if hostname is not None else None
    session: requests.Session | None = None
    if resolve_hostname and hostname is not None:
        # Address the gateway by hostname (resolved to its IP) so the TLS SNI carries the
        # hostname, which hostname-scoped HTTPS listeners require to select the right route.
        session = requests.Session()
        session.mount(f"{scheme}://{hostname}", DNSResolverAdapter(hostname, gateway_address))
        url = f"{scheme}://{hostname}{path}"
    else:
        url = f"{scheme}://{gateway_address}{path}"

    @retry(
        retry=retry_if_exception_type((AssertionError, requests.exceptions.RequestException)),
        wait=wait_fixed(5),
        stop=stop_after_delay(timeout),
        reraise=True,
    )
    def _request() -> requests.Response:
        """Issue the request once and assert the response.

        Returns:
            The :class:`requests.Response` once it matches the expectations.

        Raises:
            AssertionError: If the response status or body does not match expectations.
        """
        requester: requests.Session = session if session is not None else requests.Session()
        response = requester.get(
            url,
            headers=headers,
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

    return _request()


def k8s_service_exists(namespace: str, name: str) -> bool:
    """Return whether a Kubernetes Service with ``name`` exists in ``namespace``.

    Used by the adapter-mode tests to distinguish the two routing branches: in the
    closed-ports branch ingress-configurator creates a selector Service named
    ``<configurator>-<backend>``; in the open-ports branch it does not (the route targets
    the backend workload's own Service instead).

    Args:
        namespace: The Kubernetes namespace (Juju model name) to look in.
        name: The Service name to check for.

    Returns:
        True if the Service exists, False otherwise.
    """
    client = Client()
    return any(
        service.metadata is not None and service.metadata.name == name
        for service in client.list(Service, namespace=namespace)
    )


def k8s_endpoint_slice_exists(namespace: str, name: str) -> bool:
    """Return whether a Kubernetes EndpointSlice with ``name`` exists in ``namespace``.

    Used by the integrator-mode assertions: in integrator mode ingress-configurator creates a
    headless Service and a matching EndpointSlice named ``<configurator>-headless`` that target
    the configured backend IPs.

    Args:
        namespace: The Kubernetes namespace (Juju model name) to look in.
        name: The EndpointSlice name to check for.

    Returns:
        True if the EndpointSlice exists, False otherwise.
    """
    client = Client()
    return any(
        slice_.metadata is not None and slice_.metadata.name == name
        for slice_ in client.list(EndpointSlice, namespace=namespace)
    )


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
