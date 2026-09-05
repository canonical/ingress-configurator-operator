# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    channel    = "latest/edge"
    # renovate: depName="ingress-configurator"
    revision = 105
  }

  assert {
    condition     = output.application.name == "ingress-configurator"
    error_message = "ingress-configurator app_name did not match expected"
  }
}
