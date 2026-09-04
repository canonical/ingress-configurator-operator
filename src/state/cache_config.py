# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Cache-config charm configuration state."""

from typing import Self, cast

import ops
from pydantic.dataclasses import dataclass

DEFAULT_HEALTHCHECK_INTERVAL_SECONDS = 10
DEFAULT_HEALTHCHECK_PATH = "/"
DEFAULT_HEALTHCHECK_VALID_STATUS = (200,)


class CacheConfigNotReadyError(Exception):
    """Raised when cache-config data is not yet usable for reconciliation.

    Carries the unit status the caller should assign at reconcile level, so that
    status assignment stays visible in the reconcile methods rather than hidden
    inside the cache-config application helper.

    Attributes:
        status: The unit status the caller should set.
    """

    def __init__(self, status: ops.StatusBase) -> None:
        """Initialize the error.

        Args:
            status: The unit status the caller should set.
        """
        super().__init__(str(status))
        self.status = status


@dataclass(frozen=True)
class CacheConfigState:
    """Charm configuration for the cache-config relation.

    All values are in the units the cache-config library expects, with the charm's
    defaults already applied. This class deliberately performs no format validation:
    validating a value belongs with publishing it, and publication is leader-only,
    so that validation lives in the library. A consequence is that a malformed value
    here blocks the leader alone; followers never reach the validation and stay active.

    Attributes:
        fail_timeout: Time before marking a backend unavailable after a failure.
        healthcheck_interval: Time between two healthchecks, in milliseconds.
        healthcheck_path: The path checked on the backends.
        healthcheck_valid_status: HTTP status codes considered healthy.
        healthcheck_ssl_verify: Whether to verify backend TLS certificates when checking.
        proxy_cache_valid: nginx cache validity rules. Empty means no rules are emitted,
            so caching defers to the backend's own Cache-Control and Expires headers.
        backend_hostname: SNI hostname for backend TLS verification, required when the
            backends use https.
    """

    fail_timeout: str
    healthcheck_interval: int
    healthcheck_path: str
    healthcheck_valid_status: list[int]
    healthcheck_ssl_verify: bool
    proxy_cache_valid: list[str]
    backend_hostname: str | None = None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase, backend_hostname: str | None = None) -> Self:
        """Build CacheConfigState from charm config.

        Defaults for the cache-specific options (``cache-fail-timeout``,
        ``cache-healthcheck-ssl-verify``) come from charmcraft.yaml, so they are always
        present. The shared ``health-check-interval`` and ``health-check-path`` options
        have no charmcraft default because haproxy-route also uses them, so they are
        defaulted here.

        Args:
            charm: The ingress-configurator charm instance.
            backend_hostname: SNI hostname to use for backend TLS verification.

        Returns:
            CacheConfigState populated from charm config.
        """
        interval_seconds = cast(int | None, charm.config.get("health-check-interval"))
        path = cast(str | None, charm.config.get("health-check-path"))
        proxy_cache_valid = cast(str | None, charm.config.get("cache-proxy-cache-valid"))
        return cls(
            fail_timeout=cast(str, charm.config["cache-fail-timeout"]),
            # `or` preserves the pre-refactor expression, which also treated a falsy
            # value as unset. A configured 0 never reaches here in practice:
            # HaproxyRouteState validates health-check-interval with gt=0 first.
            healthcheck_interval=(interval_seconds or DEFAULT_HEALTHCHECK_INTERVAL_SECONDS) * 1000,
            healthcheck_path=path or DEFAULT_HEALTHCHECK_PATH,
            healthcheck_valid_status=list(DEFAULT_HEALTHCHECK_VALID_STATUS),
            healthcheck_ssl_verify=cast(bool, charm.config["cache-healthcheck-ssl-verify"]),
            proxy_cache_valid=[proxy_cache_valid] if proxy_cache_valid else [],
            backend_hostname=backend_hostname,
        )
