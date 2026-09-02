# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for CacheConfigState."""

import json
from unittest.mock import MagicMock

import ops

from state.cache_config import CacheConfigState


def _make_charm(config: dict) -> MagicMock:
    # Mirror the charmcraft.yaml defaults that Juju always applies for cache-specific options.
    merged = {"cache-fail-timeout": "30s", "cache-healthcheck-ssl-verify": True, **config}
    charm = MagicMock(spec=ops.CharmBase)
    charm.config = merged
    return charm


def test_build_with_no_config():
    """
    arrange: charm with no user-set cache config (only charmcraft defaults applied).
    act: build CacheConfigState.
    assert: shared optional fields are None; cache-specific fields carry charmcraft defaults.
    """
    charm = _make_charm({})
    state = CacheConfigState.build(charm)
    assert state.proxy_cache_valid is None
    assert state.healthcheck_interval is None
    assert state.healthcheck_path is None
    assert state.fail_timeout == "30s"
    assert state.healthcheck_ssl_verify is True


def test_build_with_all_config():
    """
    arrange: charm with cache-proxy-cache-valid, health-check-interval, health-check-path set.
    act: build CacheConfigState.
    assert: fields are populated from config.
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
    state = CacheConfigState.build(charm)
    assert state.proxy_cache_valid == "200 1h"
    assert state.healthcheck_interval == 5
    assert state.healthcheck_path == "/health"
    assert state.fail_timeout == "1m"
    assert state.healthcheck_ssl_verify is False


def test_to_relation_data_minimal():
    """
    arrange: CacheConfigState with no optional fields.
    act: call to_relation_data with one backend URL.
    assert: dict contains backends, default healthcheck fields, proxy_cache_valid as empty list.
    """
    state = CacheConfigState(
        proxy_cache_valid=None,
        healthcheck_interval=None,
        healthcheck_path=None,
        fail_timeout="30s",
        healthcheck_ssl_verify=True,
    )
    data = state.to_relation_data(["http://10.0.0.1:8080"])
    assert json.loads(data["backends"]) == ["http://10.0.0.1:8080"]
    assert "backend_hostname" not in data
    assert data["fail_timeout"] == "30s"
    assert data["healthcheck_interval"] == "10000"  # None → 10 * 1000ms
    assert data["healthcheck_path"] == "/"
    assert json.loads(data["healthcheck_valid_status"]) == [200]
    assert data["healthcheck_ssl_verify"] == "true"
    assert json.loads(data["proxy_cache_valid"]) == []


def test_to_relation_data_with_all_options():
    """
    arrange: CacheConfigState with all optional fields set, including ssl_verify disabled.
    act: call to_relation_data with multiple backends.
    assert: dict contains all fields correctly serialised.
    """
    state = CacheConfigState(
        proxy_cache_valid="200 1h",
        healthcheck_interval=5,
        healthcheck_path="/health",
        fail_timeout="1m",
        healthcheck_ssl_verify=False,
    )
    data = state.to_relation_data(["http://10.0.0.1:8080", "http://10.0.0.2:8080"])
    assert json.loads(data["backends"]) == ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]
    assert "backend_hostname" not in data
    assert data["fail_timeout"] == "1m"
    assert data["healthcheck_interval"] == "5000"  # 5s → 5000ms
    assert data["healthcheck_path"] == "/health"
    assert data["healthcheck_ssl_verify"] == "false"
    assert json.loads(data["proxy_cache_valid"]) == ["200 1h"]


def test_to_relation_data_with_backend_hostname():
    """
    arrange: CacheConfigState with backend_hostname set.
    act: call to_relation_data.
    assert: backend_hostname is present in the relation data.
    """
    state = CacheConfigState(
        proxy_cache_valid=None,
        healthcheck_interval=None,
        healthcheck_path=None,
        fail_timeout="30s",
        healthcheck_ssl_verify=True,
        backend_hostname="cache.example.com",
    )
    data = state.to_relation_data(["http://10.0.0.1:8080"])
    assert data["backend_hostname"] == "cache.example.com"


def test_get_cache_backends_returns_none_when_no_units():
    """
    arrange: relation with no remote units.
    act: call get_cache_backends.
    assert: returns None.
    """
    rel = MagicMock(spec=ops.Relation)
    rel.units = set()
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_none_when_field_missing():
    """
    arrange: relation with one remote unit whose databag has no cache-backend key.
    act: call get_cache_backends.
    assert: returns None.
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_none_when_empty_string():
    """
    arrange: content-cache has cleared cache-backend (empty string sentinel).
    act: call get_cache_backends.
    assert: returns None (treat cleared as not-available).
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backend": ""}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_none_when_whitespace_only():
    """
    arrange: content-cache wrote only whitespace to cache-backend.
    act: call get_cache_backends.
    assert: returns None.
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backend": "   "}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_urls():
    """
    arrange: content-cache has written a plain URL to cache-backend.
    act: call get_cache_backends.
    assert: returns the URL in a list.
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backend": "http://10.1.0.5:8080"}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result == ["http://10.1.0.5:8080"]


def test_get_cache_backends_aggregates_multiple_units():
    """
    arrange: two content-cache units each with a cache-backend URL.
    act: call get_cache_backends.
    assert: returns all URLs combined.
    """
    unit1 = MagicMock(spec=ops.Unit)
    unit2 = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit1, unit2}
    rel.data = {
        unit1: {"cache-backend": "http://10.1.0.5:30000"},
        unit2: {"cache-backend": "http://10.1.0.6:30000"},
    }
    result = CacheConfigState.get_cache_backends(rel)
    assert result is not None
    assert sorted(result) == ["http://10.1.0.5:30000", "http://10.1.0.6:30000"]
