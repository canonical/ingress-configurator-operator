# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Contract tests for substrate-specific integration model fixtures."""

import ast
from pathlib import Path

INTEGRATION_DIR = Path(__file__).parent
TESTS_CONFTEST = INTEGRATION_DIR.parent / "conftest.py"


def test_shared_conftest_owns_explicit_model_fixtures() -> None:
    """Shared fixtures create lazy temporary models on explicit controllers."""
    source = (INTEGRATION_DIR / "conftest.py").read_text(encoding="utf-8")

    assert 'name="juju_lxd"' in source
    assert 'name="juju_k8s"' in source
    assert 'name="juju"' not in source
    assert 'controller="concierge-lxd"' in source
    assert 'controller="concierge-k8s"' in source


def test_keep_models_option_is_registered() -> None:
    """Temporary models can be retained for debugging."""
    source = TESTS_CONFTEST.read_text(encoding="utf-8")

    assert 'parser.addoption("--keep-models", action="store_true", default=False)' in source


def test_suite_directories_do_not_define_model_fixtures() -> None:
    """Suite directories inherit lazy model fixtures from the shared conftest."""
    for suite in ("lxd", "k8s", "k8s_lxd"):
        assert not (INTEGRATION_DIR / suite / "conftest.py").exists()


def test_no_integration_fixture_or_test_requests_generic_juju() -> None:
    """Model dependencies must identify their substrate in the fixture name."""
    python_files = [INTEGRATION_DIR / "conftest.py"]
    python_files.extend(INTEGRATION_DIR.glob("*/conftest.py"))
    python_files.extend(INTEGRATION_DIR.glob("*/test_*.py"))

    for path in python_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_fixture = any(
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "fixture"
                    for decorator in node.decorator_list
                )
                if not is_fixture and not node.name.startswith("test_"):
                    continue
                argument_names = {argument.arg for argument in node.args.args}
                assert "juju" not in argument_names, (
                    f"generic juju argument in {path}:{node.lineno}"
                )


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
