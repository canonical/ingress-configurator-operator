#!/bin/bash

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

set -u

# lxd should be install and init by a previous step in integration test action.
echo "bootstrapping lxd juju controller"
juju bootstrap localhost localhost
juju add-cloud --controller localhost k8s
juju add-model k8s k8s
