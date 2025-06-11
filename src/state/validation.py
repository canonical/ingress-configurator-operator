# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for functions containing charm utilities."""

import functools
import logging
import typing

import ops

from state.integrator import InvalidIntegratorConfigError

logger = logging.getLogger(__name__)

C = typing.TypeVar("C", bound=ops.CharmBase)


def validate_config(
    method: typing.Callable[[C, typing.Any], None],
) -> typing.Callable[[C, typing.Any], None]:
    """Create a decorator that puts the charm in blocked state if the config is wrong.

    Args:
        method: observer method to wrap.

    Returns:
        the function wrapper.
    """

    @functools.wraps(method)
    def wrapper(instance: C, *args: typing.Any) -> None:
        """Block the charm if the config is wrong.

        Args:
            instance: the instance of the class with the hook method.
            args: Additional events

        Returns:
            The value returned from the original function. That is, None.
        """
        try:
            return method(instance, *args)
        except InvalidIntegratorConfigError as exc:
            instance.unit.status = ops.BlockedStatus(str(exc))
            logger.exception("Error configuring the integrator mode.")
            return None

    return wrapper
