# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for CacheConfigState."""

import json
from unittest.mock import MagicMock

import ops
import pytest

from state.cache_config import CacheConfigState


def _make_charm(config: dict) -> MagicMock:
    charm = MagicMock(spec=ops.CharmBase)
    charm.config = config
    return charm


def test_build_with_no_config():
    """
    arrange: charm with no cache-related config set.
    act: build CacheConfigState.
    assert: all optional fields are None.
    """
    charm = _make_charm({})
    state = CacheConfigState.build(charm)
    assert state.proxy_cache_valid is None
    assert state.healthcheck_interval is None
    assert state.healthcheck_path is None


def test_build_with_all_config():
    """
    arrange: charm with proxy-cache-valid, health-check-interval, health-check-path set.
    act: build CacheConfigState.
    assert: fields are populated from config.
    """
    charm = _make_charm(
        {
            "proxy-cache-valid": "200 1h",
            "health-check-interval": 5,
            "health-check-path": "/health",
        }
    )
    state = CacheConfigState.build(charm)
    assert state.proxy_cache_valid == "200 1h"
    assert state.healthcheck_interval == 5
    assert state.healthcheck_path == "/health"


def test_to_relation_data_minimal():
    """
    arrange: CacheConfigState with no optional fields.
    act: call to_relation_data with one backend URL.
    assert: dict contains backends, default healthcheck fields, no proxy_cache_valid.
    """
    state = CacheConfigState(
        proxy_cache_valid=None,
        healthcheck_interval=None,
        healthcheck_path=None,
    )
    data = state.to_relation_data(["http://10.0.0.1:8080"])
    assert json.loads(data["backends"]) == ["http://10.0.0.1:8080"]
    assert data["healthcheck_interval"] == "10000"  # None → 10 * 1000ms
    assert data["healthcheck_path"] == "/"
    assert json.loads(data["healthcheck_valid_status"]) == [200]
    assert "proxy_cache_valid" not in data


def test_to_relation_data_with_all_options():
    """
    arrange: CacheConfigState with all optional fields set.
    act: call to_relation_data with multiple backends.
    assert: dict contains all fields correctly serialised.
    """
    state = CacheConfigState(
        proxy_cache_valid="200 1h",
        healthcheck_interval=5,
        healthcheck_path="/health",
    )
    data = state.to_relation_data(["http://10.0.0.1:8080", "http://10.0.0.2:8080"])
    assert json.loads(data["backends"]) == ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]
    assert data["healthcheck_interval"] == "5000"  # 5s → 5000ms
    assert data["healthcheck_path"] == "/health"
    assert json.loads(data["proxy_cache_valid"]) == ["200 1h"]


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
    arrange: relation with one remote unit whose databag has no cache-backends key.
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
    arrange: content-cache has cleared cache-backends (empty string sentinel).
    act: call get_cache_backends.
    assert: returns None (treat cleared as not-available).
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backends": ""}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_none_when_empty_list():
    """
    arrange: content-cache wrote an empty JSON list.
    act: call get_cache_backends.
    assert: returns None.
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backends": "[]"}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result is None


def test_get_cache_backends_returns_urls():
    """
    arrange: content-cache has written valid cache-backends JSON.
    act: call get_cache_backends.
    assert: returns the parsed list of URLs.
    """
    unit = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit}
    rel.data = {unit: {"cache-backends": '["http://10.1.0.5:8080"]'}}
    result = CacheConfigState.get_cache_backends(rel)
    assert result == ["http://10.1.0.5:8080"]


def test_get_cache_backends_aggregates_multiple_units():
    """
    arrange: two content-cache units each with one cache-backend URL.
    act: call get_cache_backends.
    assert: returns all URLs combined.
    """
    unit1 = MagicMock(spec=ops.Unit)
    unit2 = MagicMock(spec=ops.Unit)
    rel = MagicMock(spec=ops.Relation)
    rel.units = {unit1, unit2}
    rel.data = {
        unit1: {"cache-backends": '["http://10.1.0.5:8080"]'},
        unit2: {"cache-backends": '["http://10.1.0.6:8080"]'},
    }
    result = CacheConfigState.get_cache_backends(rel)
    assert result is not None
    assert sorted(result) == ["http://10.1.0.5:8080", "http://10.1.0.6:8080"]
