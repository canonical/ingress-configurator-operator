# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for CacheConfigState."""

from unittest.mock import MagicMock

import ops

from state.cache_config import CacheConfigState


def _make_charm(config: dict) -> MagicMock:
    # Mirror the charmcraft.yaml defaults that Juju always applies for cache-specific options.
    merged = {"cache-fail-timeout": "30s", "cache-healthcheck-ssl-verify": True, **config}
    charm = MagicMock(spec=ops.CharmBase)
    charm.config = merged
    return charm


def test_build_applies_defaults():
    """
    arrange: charm with no user-set cache config (only charmcraft defaults applied).
    act: build CacheConfigState.
    assert: healthcheck defaults are applied and the interval is converted to milliseconds.
    """
    state = CacheConfigState.from_charm(_make_charm({}))
    assert state.fail_timeout == "30s"
    assert state.healthcheck_interval == 10000
    assert state.healthcheck_path == "/"
    assert state.healthcheck_valid_status == [200]
    assert state.healthcheck_ssl_verify is True
    assert state.proxy_cache_valid == []
    assert state.backend_hostname is None


def test_build_with_all_config():
    """
    arrange: charm with every cache-related config option set.
    act: build CacheConfigState.
    assert: fields are populated from config, in the units the library expects.
    """
    charm = _make_charm(
        {
            "cache-proxy-cache-valid": "200 1h",
            "health-check-interval": 5,
            "health-check-path": "/health",
            "cache-fail-timeout": "1m",
            "cache-healthcheck-ssl-verify": False,
        }
    )
    state = CacheConfigState.from_charm(charm)
    assert state.fail_timeout == "1m"
    assert state.healthcheck_interval == 5000
    assert state.healthcheck_path == "/health"
    assert state.healthcheck_ssl_verify is False
    assert state.proxy_cache_valid == ["200 1h"]


def test_build_passes_backend_hostname_through():
    """
    arrange: a charm and a backend hostname resolved from the haproxy-route state.
    act: build CacheConfigState with that hostname.
    assert: the hostname is carried on the state.
    """
    state = CacheConfigState.from_charm(_make_charm({}), backend_hostname="cache.example.com")
    assert state.backend_hostname == "cache.example.com"


def test_build_keeps_invalid_fail_timeout_for_the_library_to_reject():
    """
    arrange: charm config with a malformed cache-fail-timeout.
    act: build CacheConfigState.
    assert: the value passes through unchanged; format validation belongs to the library.
    """
    state = CacheConfigState.from_charm(_make_charm({"cache-fail-timeout": "not-a-time"}))
    assert state.fail_timeout == "not-a-time"
