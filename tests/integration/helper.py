# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for integration tests."""

from urllib.parse import urlparse

from requests import Response, Session
from requests.adapters import DEFAULT_POOLBLOCK, DEFAULT_POOLSIZE, HTTPAdapter
from urllib3.util.retry import Retry


class DNSResolverHTTPSAdapter(HTTPAdapter):
    """A simple mounted DNS resolver for HTTP requests, with retry support."""

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        hostname,
        ip,
        retries: int = 5,
        backoff_factor: float = 1.0,
        status_forcelist: tuple = (502, 503, 504),
    ):
        """Initialize the DNS resolver with retry configuration.

        Args:
            hostname: DNS entry to resolve.
            ip: Target IP address.
            retries: Number of times to retry on failure.
            backoff_factor: Time to wait between retries (with exponential backoff).
            status_forcelist: HTTP status codes that should trigger a retry.
        """
        self.hostname = hostname
        self.ip = ip

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["GET"],
            raise_on_status=False,
        )

        super().__init__(
            max_retries=retry_strategy,
            pool_connections=DEFAULT_POOLSIZE,
            pool_maxsize=DEFAULT_POOLSIZE,
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


def haproxy_request(session: Session, url: str) -> Response:
    """Make a request to the HAProxy service.

    Args:
        session: Requests session with custom DNS resolution.
        url: URL to request from the HAProxy service.

    Returns:
        Response: HTTP response from the HAProxy service.
    """
    return session.get(
        url,
        timeout=30,
        verify=False,  # nosec - calling charm ingress URL
    )
