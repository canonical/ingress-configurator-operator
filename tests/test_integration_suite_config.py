# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Contract tests for integration suite provisioning configuration."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parent.parent


def _load_yaml(relative_path: str) -> dict:
    """Load a YAML mapping from the repository root."""
    return yaml.safe_load((REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"))


def test_concierge_configs_provision_only_required_substrates() -> None:
    """Each Concierge configuration enables exactly its suite's providers."""
    expected_providers = {
        "concierge-lxd-juju4.yaml": {"lxd"},
        "concierge-k8s-juju4.yaml": {"k8s"},
        "concierge-k8s-lxd-juju4.yaml": {"k8s", "lxd"},
    }

    for config_path, expected in expected_providers.items():
        config = _load_yaml(config_path)
        assert set(config["providers"]) == expected


def test_spread_suites_match_test_substrates() -> None:
    """Spread discovers each test group with the corresponding Concierge config."""
    spread = _load_yaml("spread.yaml")
    expected_suites = {
        "tests/integration-lxd-juju4/": (
            "tests/integration/lxd/",
            "concierge-lxd-juju4.yaml",
        ),
        "tests/integration-k8s-juju4/": (
            "tests/integration/k8s/",
            "concierge-k8s-juju4.yaml",
        ),
        "tests/integration-k8s-lxd-juju4/": (
            "tests/integration/k8s_lxd/",
            "concierge-k8s-lxd-juju4.yaml",
        ),
    }

    assert set(spread["integration-suites"]) == set(expected_suites)
    for suite_name, (discover_path, concierge) in expected_suites.items():
        suite = spread["integration-suites"][suite_name]
        assert suite["discover-path"] == discover_path
        assert suite["environment"]["CONCIERGE"] == concierge
