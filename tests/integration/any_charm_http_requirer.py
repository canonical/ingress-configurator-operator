# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""HTTP requirer source."""

from any_charm_base import AnyCharmBase  # type: ignore

from helper import start_http_server


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Ingress requirer charm src."""

    def start_server(self):
        """Start apache2 webserver."""
        start_http_server()
