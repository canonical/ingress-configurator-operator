# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Cache-config relation state management module."""

import json
import logging
from typing import Self, cast

import ops
from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)

CACHE_CONFIG_RELATION_NAME = "cache-config"


@dataclass(frozen=True)
class CacheConfigState:
    """State for the cache-config relation.

    Attributes:
        proxy_cache_valid: Cache validity rule, e.g. "200 1h". None means not configured.
        healthcheck_interval: Health check interval in seconds, from charm config.
        healthcheck_path: Health check path, from charm config.
        fail_timeout: Time before marking a backend as unavailable after failure. Always set;
            charmcraft.yaml defines the default (``cache-fail-timeout``).
        healthcheck_ssl_verify: Whether to verify TLS certificates during health checks. Always
            set; charmcraft.yaml defines the default (``cache-healthcheck-ssl-verify``).
        backend_hostname: SNI hostname for backend TLS verification. Required when backends
            use https://. Matches the hostname in the backend's TLS certificate.
    """

    proxy_cache_valid: str | None
    healthcheck_interval: int | None
    healthcheck_path: str | None
    fail_timeout: str
    healthcheck_ssl_verify: bool
    backend_hostname: str | None = None

    @classmethod
    def build(cls, charm: ops.CharmBase, backend_hostname: str | None = None) -> Self:
        """Build CacheConfigState from charm config.

        Defaults for cache-specific options (``cache-fail-timeout``,
        ``cache-healthcheck-ssl-verify``) are defined in charmcraft.yaml, so they are always
        present in ``charm.config``. The shared ``health-check-interval``/``health-check-path``
        options have no charmcraft default (they are also used by haproxy-route), so they may be
        ``None`` here and are defaulted at serialization time in ``to_relation_data``.

        Args:
            charm: The ingress-configurator charm instance.
            backend_hostname: SNI hostname to use for backend TLS verification when backends
                use https://. Typically the service hostname from the ingress state.

        Returns:
            CacheConfigState populated from charm config.
        """
        return cls(
            proxy_cache_valid=cast(str | None, charm.config.get("cache-proxy-cache-valid")),
            healthcheck_interval=cast(int | None, charm.config.get("health-check-interval")),
            healthcheck_path=cast(str | None, charm.config.get("health-check-path")),
            fail_timeout=cast(str, charm.config["cache-fail-timeout"]),
            healthcheck_ssl_verify=cast(bool, charm.config["cache-healthcheck-ssl-verify"]),
            backend_hostname=backend_hostname,
        )

    def to_relation_data(self, backends: list[str]) -> dict[str, str]:
        """Build the dict to write into the requirer app databag.

        Args:
            backends: List of backend URLs, e.g. ["http://10.0.0.1:8080"].

        Returns:
            Dict of string key/value pairs to write to the relation databag.
        """
        data: dict[str, str] = {
            "backends": json.dumps(backends),
            "fail_timeout": self.fail_timeout,
            # health-check-interval/path are shared with haproxy-route and have no charmcraft
            # default, so fall back to nginx-sensible defaults (10s interval, "/" path) here.
            "healthcheck_interval": str((self.healthcheck_interval or 10) * 1000),
            "healthcheck_path": self.healthcheck_path or "/",
            "healthcheck_valid_status": json.dumps([200]),
            "healthcheck_ssl_verify": json.dumps(self.healthcheck_ssl_verify),
            "proxy_cache_valid": json.dumps(
                [self.proxy_cache_valid] if self.proxy_cache_valid else []
            ),
        }
        if self.backend_hostname:
            data["backend_hostname"] = self.backend_hostname
        return data

    @staticmethod
    def get_cache_backends(rel: ops.Relation) -> list[str] | None:
        """Read cache-backend from all content-cache unit databags.

        content-cache writes a single plain URL string to the ``cache-backend`` key
        of its own unit databag. An empty string sentinel means the relation was cleared.
        The returned list is sorted so the resulting backend order is deterministic across
        hook executions (``rel.units`` is a set with no guaranteed iteration order),
        avoiding needless haproxy config churn.

        Args:
            rel: The cache-config relation.

        Returns:
            List of cache-backend URLs if available, None otherwise.
        """
        all_backends: list[str] = []
        for unit in rel.units:
            raw = rel.data[unit].get("cache-backend", "").strip()
            if raw:
                all_backends.append(raw)
            else:
                logger.debug("Unit %s has no cache-backend in databag", unit)
        return sorted(all_backends) if all_backends else None
