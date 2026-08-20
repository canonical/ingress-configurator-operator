# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "The deployed ingress-configurator application."
  value       = juju_application.ingress-configurator
}

output "provides" {
  description = "Map of the provided integration endpoints."
  value = {
    ingress = {
      kind     = "endpoint"
      name     = juju_application.ingress-configurator.name
      endpoint = "ingress"
    }
  }
}

output "requires" {
  description = "Map of the required integration endpoints."
  value = {
    gateway_route = {
      kind     = "endpoint"
      name     = juju_application.ingress-configurator.name
      endpoint = "gateway-route"
    }
    haproxy_route = {
      kind     = "endpoint"
      name     = juju_application.ingress-configurator.name
      endpoint = "haproxy-route"
    }
    haproxy_route_tcp = {
      kind     = "endpoint"
      name     = juju_application.ingress-configurator.name
      endpoint = "haproxy-route-tcp"
    }
  }
}
