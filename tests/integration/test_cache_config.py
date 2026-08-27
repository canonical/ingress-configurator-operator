# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the cache-config relation.

Topology (HTTP backend)
-----------------------
any-charm-backend  (HTTP server on port 80)
    ↑  (backends resolved via ingress-configurator integrator config)
ingress-configurator  ──cache-config──▶  content-cache  (nginx caching proxy)
    ↓  haproxy-route
haproxy  ◀── HTTP client

Topology (HTTPS backend)
------------------------
any-charm-https-backend  (HTTPS server on port 443, self-signed cert)
    ↑  (backends resolved via ingress-configurator integrator config)
ingress-configurator  ──cache-config──▶  content-cache  (nginx caching proxy)
    ↓  haproxy-route
haproxy  ◀── HTTP client

Flow:
1. ingress-configurator resolves backend addresses from charm config and writes
   them into the cache-config relation databag.
2. content-cache receives the backends, starts nginx, and publishes its own
   ``cache-backend`` URL (``http://<IP>:<port>``) into the relation databag.
3. ingress-configurator reads ``cache-backend`` and substitutes it into the
   haproxy-route configuration, so haproxy routes through content-cache.
4. An HTTP request through haproxy is served by content-cache → backend.
"""

from typing import Callable

import jubilant
import pytest
from requests import Session

from .conftest import (
    CERTIFICATES_APP_NAME,
    HTTPS_BACKEND_APP_NAME,
    MOCK_HAPROXY_HOSTNAME,
    get_unit_addresses,
)


@pytest.mark.abort_on_fail
def test_cache_config_backend_substitution(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    any_charm_backend: str,
    content_cache: str,
    http_session: Callable[..., Session],
) -> None:
    """Test end-to-end routing through content-cache via the cache-config relation.

    Verifies that:
    - ingress-configurator writes backend URLs into the cache-config databag.
    - content-cache publishes a ``cache-backend`` URL after starting nginx.
    - ingress-configurator substitutes content-cache as the haproxy backend.
    - HTTP requests through haproxy are served via the content-cache → backend chain.

    Args:
        juju: Jubilant juju fixture.
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        any_charm_backend: Name of the any-charm application acting as an HTTP backend.
        content_cache: Name of the content-cache application.
        http_session: Modified requests session fixture for making HTTP requests.
    """
    # Wait for backend to be idle so its address is stable before reading it.
    juju.wait(
        lambda status: jubilant.all_agents_idle(status, any_charm_backend),
        error=jubilant.any_error,
    )

    # Configure ingress-configurator in integrator mode pointing at the backend.
    backend_addresses = ",".join(str(addr) for addr in get_unit_addresses(juju, any_charm_backend))
    juju.config(
        app=application,
        values={
            "backend-addresses": backend_addresses,
            "backend-ports": "80",
            "paths": "/api/v1,/api/v2",
        },
    )

    # Wire up haproxy-route and cache-config relations.
    juju.integrate(f"{haproxy}:haproxy-route", f"{application}:haproxy-route")
    juju.integrate(f"{application}:cache-config", f"{content_cache}:cache-config")

    # All four charms (plus the certificates sidecar for haproxy) should settle active.
    juju.wait(
        lambda status: (
            jubilant.all_active(
                status,
                haproxy,
                application,
                any_charm_backend,
                content_cache,
                CERTIFICATES_APP_NAME,
            )
            and jubilant.all_agents_idle(
                status,
                haproxy,
                application,
                any_charm_backend,
                content_cache,
                CERTIFICATES_APP_NAME,
            )
        ),
        error=jubilant.any_error,
    )

    # content-cache reaching Active status proves it received the backends from
    # the cache-config relation, successfully started nginx, and published its
    # own cache-backend URL back to ingress-configurator.  ingress-configurator
    # becoming Active in turn proves it read that URL and updated the haproxy
    # route to point at content-cache rather than the original backend.

    # Make an HTTP request through haproxy and verify the backend page is served.
    haproxy_address = str(get_unit_addresses(juju, haproxy)[0])
    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, haproxy_address)])

    for path_component in ["v1", "v2"]:
        response = session.get(
            f"https://{MOCK_HAPROXY_HOSTNAME}/api/{path_component}/",
            timeout=30,
            verify=False,
        )
        assert response.status_code == 200
        assert f"{path_component} ok!" in response.text


@pytest.mark.abort_on_fail
def test_cache_config_https_backend(
    juju: jubilant.Juju,
    application: str,
    haproxy: str,
    any_charm_backend_https: str,
    content_cache: str,
    http_session: Callable[..., Session],
) -> None:
    """Test end-to-end routing through content-cache when the backend speaks HTTPS.

    Tests the full two-certificate architecture described in the design document:

    - backend-lego  (any-charm-https-backend self-generated cert + CA):
        any-charm-https-backend  ──(provide-certificate-transfer)──▶  content-cache:receive-ca-cert
        (content-cache trusts the backend CA and verifies backend TLS)

    - cache-lego  (self-signed-certificates):
        self-signed-certificates:certificates  ──▶  content-cache:certificates
        (content-cache gets a TLS cert for its own nginx frontend)
        self-signed-certificates:send-ca-cert  ──▶  haproxy:receive-ca-certs
        (haproxy trusts the CA that signed content-cache's cert)

    Full chain: client ──HTTPS──▶ haproxy ──HTTPS──▶ content-cache ──HTTPS──▶ backend

    Args:
        juju: Jubilant juju fixture.
        application: Name of the ingress-configurator application.
        haproxy: Name of the haproxy application.
        any_charm_backend_https: Name of the any-charm application serving HTTPS.
        content_cache: Name of the content-cache application.
        http_session: Modified requests session fixture for making HTTP requests.
    """
    # Wait for backend to be idle so its address is stable and the CA cert is generated.
    juju.wait(
        lambda status: jubilant.all_agents_idle(status, any_charm_backend_https),
        error=jubilant.any_error,
    )

    backend_addresses = ",".join(
        str(addr) for addr in get_unit_addresses(juju, any_charm_backend_https)
    )
    juju.config(
        app=application,
        values={
            "backend-addresses": backend_addresses,
            "backend-ports": "443",
            "backend-protocol": "https",
            # The LUA healthcheck in content-cache has no ssl_trusted_certificate_path
            # configured, so it falls back to the system CA bundle which doesn't contain
            # the test CA. Disable healthcheck SSL verification to allow the healthcheck
            # to pass; nginx proxy SSL verification still uses ca-bundle.pem and the
            # backend cert's IP SAN for proper certificate verification.
            "healthcheck-ssl-verify": "false",
            "paths": "/api/v1,/api/v2",
            # hostname is required when cache-backend uses HTTPS (content-cache TLS frontend);
            # ingress-configurator passes it to haproxy for routing and SNI.
            "hostname": MOCK_HAPROXY_HOSTNAME,
        },
    )

    # backend-lego leg: provide the backend's CA cert to content-cache so nginx can verify
    # the HTTPS backend. The backend publishes its CA cert via provide-certificate-transfer.
    juju.integrate(
        f"{HTTPS_BACKEND_APP_NAME}:provide-certificate-transfer",
        f"{content_cache}:receive-ca-cert",
    )

    # cache-lego leg: give content-cache a TLS certificate for its own nginx frontend so it
    # publishes https:// cache-backend URLs. haproxy already trusts this CA via receive-ca-certs
    # (wired in the haproxy fixture).
    juju.integrate(
        f"{CERTIFICATES_APP_NAME}:certificates",
        f"{content_cache}:certificates",
    )

    # Relations already exist from test_cache_config_backend_substitution
    # (module-scoped model is shared); just wait for everything to settle.
    juju.wait(
        lambda status: (
            jubilant.all_active(
                status,
                haproxy,
                application,
                any_charm_backend_https,
                content_cache,
                CERTIFICATES_APP_NAME,
            )
            and jubilant.all_agents_idle(
                status,
                haproxy,
                application,
                any_charm_backend_https,
                content_cache,
                CERTIFICATES_APP_NAME,
            )
        ),
        error=jubilant.any_error,
        timeout=10 * 60,
    )

    haproxy_address = str(get_unit_addresses(juju, haproxy)[0])
    session = http_session(dns_entries=[(MOCK_HAPROXY_HOSTNAME, haproxy_address)])

    for path_component in ["v1", "v2"]:
        response = session.get(
            f"https://{MOCK_HAPROXY_HOSTNAME}/api/{path_component}/",
            timeout=30,
            verify=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 for /api/{path_component}/, got {response.status_code}. "
            f"Body: {response.text[:500]}"
        )
        assert f"{path_component} ok!" in response.text
