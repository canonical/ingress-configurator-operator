---
myst:
  html_meta:
    "description lang=en": "A Juju charm that configures route-provider interfaces (haproxy-route, haproxy-route-tcp, gateway-route) for both charm workloads via the ingress interface and external backends via configuration."
---
# Ingress configurator operator

The ingress configurator operator is a Juju charm that acts as a bridge between workloads needing ingress and the route-provider charms that fulfill it. It supports both charm workloads integrating over the `ingress` interface and external backends described by configuration.

The following route-provider interfaces are supported:

- `haproxy-route` and `haproxy-route-tcp` for HAProxy-based deployments.
- `gateway-route` for Kubernetes Gateway API deployments.

## In this documentation

```{list-table}
   :header-rows: 1
   :widths: 15 30

* - 
  - 
* - **Get started**
  - {ref}`tutorial_getting_started`
* - **Operations**
  - {ref}`Route HTTP traffic to a non-charmed workload <how_to_haproxy_integrate_non_charm_workload>` | {ref}`Route TCP traffic to a non-charmed workload <how_to_haproxy_integrate_tcp_non_charm_workload>` | {ref}`Add HAProxy features to an ingress requirer <how_to_add_haproxy_features_to_ingress_requirer>` | {ref}`Load balance a gRPC server <how_to_haproxy_loadbalancing_grpc>` | {ref}`Upgrade <how_to_upgrade>`
* - **Explanation**
  - {ref}`How gateway-route works <explanation_gateway_route>`
```

```{toctree}
:hidden:
tutorial/index.md
how-to/index.md
explanation/index.md
release-notes/index.md
changelog.md
```
