# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the ingress-per-unit gateway-route state builder."""

from unittest.mock import MagicMock

import pytest

from state.gateway_route import (
    GatewayRoutePerUnitBackend,
    GatewayRoutePerUnitState,
    InvalidGatewayRouteStateError,
)


def _charm(model_name="testing", config=None):
    charm = MagicMock()
    charm.model.name = model_name
    charm.config = config or {}
    return charm


def _provider(units_data):
    """units_data: {unit_name: {"name","model","port","strip-prefix"}}."""
    provider = MagicMock()
    units = []
    for unit_name in units_data:
        unit = MagicMock()
        unit.name = unit_name
        units.append(unit)
    relation = MagicMock()
    relation.units = units
    provider.is_unit_ready.return_value = True
    provider.get_data.side_effect = lambda rel, unit: units_data[unit.name]
    return provider, relation


def test_build_from_provider_computes_pod_name_and_path():
    provider, relation = _provider(
        {
            "requirer/0": {
                "name": "requirer/0",
                "model": "testing",
                "port": 8080,
                "strip-prefix": True,
            },
            "requirer/1": {
                "name": "requirer/1",
                "model": "testing",
                "port": 8080,
                "strip-prefix": False,
            },
        }
    )
    charm = _charm(config={"hostname": "example.com"})

    state = GatewayRoutePerUnitState.build_from_provider(charm, provider, relation)

    assert state.hostname == "example.com"
    assert state.hostnames == ["example.com"]
    assert sorted(state.backends, key=lambda b: b.unit_name) == [
        GatewayRoutePerUnitBackend(
            unit_name="requirer/0",
            pod_name="requirer-0",
            path="/testing-requirer/0",
            port=8080,
            strip_prefix=True,
        ),
        GatewayRoutePerUnitBackend(
            unit_name="requirer/1",
            pod_name="requirer-1",
            path="/testing-requirer/1",
            port=8080,
            strip_prefix=False,
        ),
    ]


def test_build_from_provider_skips_unready_units():
    provider, relation = _provider(
        {
            "requirer/0": {
                "name": "requirer/0",
                "model": "testing",
                "port": 8080,
                "strip-prefix": False,
            }
        }
    )
    provider.is_unit_ready.return_value = False
    charm = _charm()

    state = GatewayRoutePerUnitState.build_from_provider(charm, provider, relation)

    assert state.backends == []


def test_build_from_provider_rejects_cross_model_unit():
    provider, relation = _provider(
        {
            "requirer/0": {
                "name": "requirer/0",
                "model": "other-model",
                "port": 8080,
                "strip-prefix": False,
            }
        }
    )
    charm = _charm(model_name="testing")

    with pytest.raises(InvalidGatewayRouteStateError):
        GatewayRoutePerUnitState.build_from_provider(charm, provider, relation)


def test_build_from_provider_rejects_invalid_port():
    provider, relation = _provider(
        {
            "requirer/0": {
                "name": "requirer/0",
                "model": "testing",
                "port": 0,
                "strip-prefix": False,
            }
        }
    )
    charm = _charm()

    with pytest.raises(InvalidGatewayRouteStateError):
        GatewayRoutePerUnitState.build_from_provider(charm, provider, relation)
