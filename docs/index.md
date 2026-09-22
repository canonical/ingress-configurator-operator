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

The documentation is grouped by the route-provider charm your deployment uses. Content that applies to both is listed in both tables.

### HAProxy operator

For deployments where the [HAProxy operator](https://charmhub.io/haproxy) provides ingress through the `haproxy-route` or `haproxy-route-tcp` interfaces.

```{list-table}
   :header-rows: 1
   :widths: 15 30

* - 
  - 
* - **Operations**
  - {ref}`Route HTTP traffic to a non-charmed workload <how_to_haproxy_integrate_non_charm_workload>` | {ref}`Route TCP traffic to a non-charmed workload <how_to_haproxy_integrate_tcp_non_charm_workload>` | {ref}`Add HAProxy features to an ingress requirer <how_to_add_haproxy_features_to_ingress_requirer>` | {ref}`Load balance a gRPC server <how_to_haproxy_loadbalancing_grpc>` | {ref}`Upgrade <how_to_upgrade>`
* - **Design**
  - {ref}`Modes of operation <explanation_modes_of_operation>`
* - **Reference**
  - {ref}`The cache-config relation <reference_cache_config>`
```

### Gateway API integrator

For deployments where the [`gateway-api-integrator`](https://charmhub.io/gateway-api-integrator) charm provides ingress through the `gateway-route` interface.

```{list-table}
   :header-rows: 1
   :widths: 15 30

* - 
  - 
* - **Get started**
  - {ref}`tutorial_getting_started`
* - **Operations**
  - {ref}`Add Kubernetes Gateway API features to an ingress requirer <how_to_add_gateway_api_features_to_ingress_requirer>` | {ref}`Route traffic for multiple workloads through a single Gateway <how_to_gateway_api_route_multiple_workloads>` | {ref}`Upgrade <how_to_upgrade>`
* - **Design**
  - {ref}`Modes of operation <explanation_modes_of_operation>` | {ref}`How gateway-route works <explanation_gateway_route>`
* - **Reference**
  - {ref}`The gateway-route relation <reference_gateway_route>`
```

```{toctree}
:hidden:
tutorial/index.md
how-to/index.md
explanation/index.md
reference/index.md
release-notes/index.md
changelog.md
```
