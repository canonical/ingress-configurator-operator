# Copyright 2025 Canonical Ltd.
# pylint: disable=import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec
# See LICENSE file for licensing details.

"""haproxy-route requirer source."""

import subprocess  # nosec

from any_charm_base import AnyCharmBase  # type: ignore


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Ingress requirer charm src."""

    def start_server(self):
        """Start apache2 webserver."""
        update = ["apt-get", "update", "--error-on=any"]
        subprocess.run(update, capture_output=True, check=True)  # nosec
        install = [
            "apt-get",
            "install",
            "-y",
            "--option=Dpkg::Options::=--force-confold",
            "apache2",
        ]
        subprocess.run(install, capture_output=True, check=True)  # nosec
