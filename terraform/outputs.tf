# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application. Deprecated: use application.name."
  value       = juju_application.ingress-configurator.name
}

output "application" {
  description = "The deployed ingress-configurator application."
  value       = juju_application.ingress-configurator
}

output "provides" {
  description = "Map of the provided integration endpoints."
  value = {
    ingress = {
      kind       = "endpoint"
      name       = juju_application.ingress-configurator.name
      endpoint   = "ingress"
      controller = null
    }
  }
}

output "requires" {
  description = "Map of the required integration endpoints."
  value = {
    gateway_route = {
      kind       = "endpoint"
      name       = juju_application.ingress-configurator.name
      endpoint   = "gateway-route"
      controller = null
    }
    haproxy_route = {
      kind       = "endpoint"
      name       = juju_application.ingress-configurator.name
      endpoint   = "haproxy-route"
      controller = null
    }
    haproxy_route_tcp = {
      kind       = "endpoint"
      name       = juju_application.ingress-configurator.name
      endpoint   = "haproxy-route-tcp"
      controller = null
    }
  }
}
