# pylint: disable=import-error
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""haproxy-route requirer source."""

import subprocess

from any_charm_base import AnyCharmBase  # type: ignore


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Ingress requirer charm src."""

    def start_server(self):
        """Start apache2 webserver."""
        update = ["apt-get", "update", "--error-on=any"]
        subprocess.run(update, capture_output=True, check=True)
        install = [
            "apt-get",
            "install",
            "-y",
            "--option=Dpkg::Options::=--force-confold",
            "apache2",
        ]
        subprocess.run(install, capture_output=True, check=True)
