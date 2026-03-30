#!/bin/bash

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

set -euo pipefail

# LXD should be installed and initialized by a previous step in the integration test action.
echo "bootstrapping lxd juju controller"
if juju show-controller localhost >/dev/null 2>&1; then
    echo "juju controller 'localhost' already exists, skipping bootstrap"
else
    juju bootstrap localhost localhost
fi
