# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Contract tests for substrate-specific integration model fixtures."""

from pathlib import Path

INTEGRATION_DIR = Path(__file__).parent
TESTS_CONFTEST = INTEGRATION_DIR.parent / "conftest.py"


def test_shared_conftest_does_not_own_models() -> None:
    """Shared fixtures must not select or create a Juju substrate."""
    source = (INTEGRATION_DIR / "conftest.py").read_text(encoding="utf-8")

    for fixture_name in (
        "lxd_controller",
        "lxd_model",
        "k8s_controller",
        "k8s_model",
        "juju",
        "juju_k8s",
    ):
        assert f'name="{fixture_name}"' not in source


def test_keep_models_option_is_registered() -> None:
    """Temporary models can be retained for debugging."""
    source = TESTS_CONFTEST.read_text(encoding="utf-8")

    assert 'parser.addoption("--keep-models", action="store_true", default=False)' in source


def test_lxd_suite_owns_only_lxd_model() -> None:
    """The machine suite creates a temporary model on the LXD controller."""
    source = (INTEGRATION_DIR / "lxd" / "conftest.py").read_text(encoding="utf-8")

    assert 'name="juju"' in source
    assert 'controller="concierge-lxd"' in source
    assert 'name="juju_k8s"' not in source


def test_k8s_suite_owns_only_k8s_model() -> None:
    """The Gateway API suite creates a model on the active K8s controller."""
    source = (INTEGRATION_DIR / "k8s" / "conftest.py").read_text(encoding="utf-8")

    assert 'name="juju"' in source
    assert 'name="juju_k8s"' in source
    assert "jubilant.temp_model(keep=keep_models)" in source
    assert "concierge-lxd" not in source


def test_cross_model_suite_owns_both_models() -> None:
    """The NodePort suite creates temporary models on both controllers."""
    source = (INTEGRATION_DIR / "k8s_lxd" / "conftest.py").read_text(encoding="utf-8")

    assert 'name="juju_k8s"' in source
    assert 'name="juju_lxd"' in source
    assert 'name="juju"' in source
    assert 'controller="concierge-k8s"' in source
    assert 'controller="concierge-lxd"' in source


def test_modules_are_grouped_by_required_substrate() -> None:
    """Each suite directory contains exactly the tests for its topology."""
    expected_modules = {
        "lxd": {
            "test_actions.py",
            "test_cache_config.py",
            "test_haproxy_adapter.py",
            "test_haproxy_integrator.py",
            "test_haproxy_route_tcp.py",
        },
        "k8s": {
            "test_gateway_route.py",
            "test_gateway_route_https.py",
        },
        "k8s_lxd": {"test_ingress_kubernetes.py"},
    }

    for suite, expected in expected_modules.items():
        actual = {path.name for path in (INTEGRATION_DIR / suite).glob("test_*.py")}
        assert actual == expected


def test_nodeport_scenario_uses_dynamic_model_clients() -> None:
    """Cross-model setup must derive its offer from temporary model clients."""
    fixture_source = (INTEGRATION_DIR / "conftest.py").read_text(encoding="utf-8")
    test_source = (INTEGRATION_DIR / "k8s_lxd" / "test_ingress_kubernetes.py").read_text(
        encoding="utf-8"
    )

    assert "juju_lxd.show_model()" in fixture_source
    assert "juju_k8s.consume(" in fixture_source
    assert "lxd_controller: str" not in fixture_source
    assert "lxd_model: str" not in fixture_source
    assert "juju_lxd: jubilant.Juju" in test_source
    assert "juju_k8s: jubilant.Juju" in test_source
    assert "lxd_controller: str" not in test_source
    assert "lxd_model: str" not in test_source
