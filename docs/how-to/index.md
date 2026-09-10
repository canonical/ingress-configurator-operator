---
myst:
  html_meta:
    "description lang=en": "How-to guides for the ingress-configurator charm."
---

(how_to_index)=

# How-to guides

These guides cover key operations and customizations for `ingress-configurator`.
Guides are grouped by which route-provider interface your deployment uses:

* **Generic** guides apply regardless of the route-provider interface in use.
* **HAProxy** guides apply to deployments using the `haproxy-route` or
  `haproxy-route-tcp` interfaces.
* **Gateway API** guides apply to deployments using the `gateway-route`
  interface.

## Generic

- {ref}`how_to_upgrade`

## HAProxy

- {ref}`how_to_haproxy_integrate_non_charm_workload`
- {ref}`how_to_haproxy_integrate_tcp_non_charm_workload`
- {ref}`how_to_add_haproxy_features_to_ingress_requirer`
- {ref}`how_to_haproxy_loadbalancing_grpc`

## Gateway API

- {ref}`how_to_add_gateway_api_features_to_ingress_requirer`
- {ref}`how_to_gateway_api_route_multiple_workloads`

```{toctree}
:hidden:
:maxdepth: 2
Upgrade <upgrade.md>
HAProxy <haproxy/index.md>
Gateway API <gateway-api/index.md>
```
