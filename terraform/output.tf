# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.ingress-configurator.name
}

output "endpoints" {
  description = "Endpoints of the deployed application."
  value = {
    ingress           = "ingress"
    haproxy_route     = "haproxy-route"
    haproxy_route_tcp = "haproxy-route-tcp"
  }
}
