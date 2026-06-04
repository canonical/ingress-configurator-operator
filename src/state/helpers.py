# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers and common utilities for the ingress-configurator-operator states."""


class InvalidStateError(Exception):
    """Exception raised when the state is invalid."""
