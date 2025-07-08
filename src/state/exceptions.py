# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more at: https://juju.is/docs/sdk


"""Exceptions for the ingress configuration information."""


class UndefinedModeError(Exception):
    """Exception raised when the charm is in an undefined state."""
