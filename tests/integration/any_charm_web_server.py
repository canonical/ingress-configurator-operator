# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error
# We use subprocess and subprocess.run to install apache
# No external inputs is parsed, ignoring bandit errors with nosec

"""Any charm web server source code."""

import pathlib
import subprocess  # nosec

import ops
from any_charm_base import AnyCharmBase  # type: ignore


class AnyCharm(AnyCharmBase):  # pylint: disable=too-few-public-methods
    """Apache web sever charm src."""

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
        base = pathlib.Path("/var/www/html/api")
        (base / "v1").mkdir(parents=True, exist_ok=True)
        (base / "v2").mkdir(parents=True, exist_ok=True)
        (base / "v1" / "index.html").write_text("v1 ok!")
        (base / "v2" / "index.html").write_text("v2 ok!")
        self.unit.status = ops.ActiveStatus("Server ready")
