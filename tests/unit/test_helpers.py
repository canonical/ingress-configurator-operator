# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the helpers module."""

from helpers import truncate_k8s_resource_name


class TestTruncateK8sResourceName:
    """Tests for truncate_k8s_resource_name."""

    def test_short_name_unchanged(self):
        """
        arrange: a name shorter than 63 characters
        act: call truncate_k8s_resource_name
        assert: the name is returned unchanged
        """
        name = "my-model-my-app-service"
        assert truncate_k8s_resource_name(name) == name

    def test_exact_63_chars_unchanged(self):
        """
        arrange: a name exactly 63 characters long
        act: call truncate_k8s_resource_name
        assert: the name is returned unchanged
        """
        name = "a" * 63
        assert truncate_k8s_resource_name(name) == name

    def test_long_name_truncated(self):
        """
        arrange: a name longer than 63 characters
        act: call truncate_k8s_resource_name
        assert: the result is at most 63 characters
        """
        name = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
        result = truncate_k8s_resource_name(name)
        assert len(result) <= 63

    def test_long_name_deterministic(self):
        """
        arrange: a name longer than 63 characters
        act: call truncate_k8s_resource_name twice
        assert: the results are identical
        """
        name = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
        assert truncate_k8s_resource_name(name) == truncate_k8s_resource_name(name)

    def test_different_long_names_produce_different_results(self):
        """
        arrange: two different names that are both longer than 63 characters
        act: call truncate_k8s_resource_name on each
        assert: the results are different
        """
        name1 = "k8s-stg-a-very-long-model-name-my-application-ingress-configurator-service"
        name2 = "k8s-stg-a-very-long-model-name-my-other-application-ingress-configurator-service"
        result1 = truncate_k8s_resource_name(name1)
        result2 = truncate_k8s_resource_name(name2)
        assert result1 != result2

    def test_truncated_name_does_not_end_with_dash_before_suffix(self):
        """
        arrange: a name that would end with a dash when truncated at the prefix boundary
        act: call truncate_k8s_resource_name
        assert: there is no double-dash in the result
        """
        # Construct a name where the truncation point falls on a dash
        name = "a" * 54 + "-" + "b" * 20
        result = truncate_k8s_resource_name(name)
        assert "--" not in result
        assert len(result) <= 63
