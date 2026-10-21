---
myst:
  html_meta:
    "description lang=en": "A Juju charm that configures route-provider interfaces (haproxy-route, haproxy-route-tcp, gateway-route) for both charm workloads via the ingress interface and external backends via configuration."
---

(index)=

# Ingress configurator operator

The ingress configurator operator is a Juju charm that acts as a bridge between workloads needing ingress and the route-provider charms that fulfill it. It supports both charm workloads integrating over the `ingress` interface and external backends described by configuration.

The following route-provider interfaces are supported:

- `haproxy-route` and `haproxy-route-tcp` for HAProxy-based deployments.
- `gateway-route` for Kubernetes Gateway API deployments.

## In this documentation

```{list-table}
   :header-rows: 1
   :widths: 15 28 28 28

* - **Type**
  - **General charm documentation**
  - **HAProxy**
  - **Gateway API integrator**
* - **Get started**
  -
  -
  - {ref}`tutorial_getting_started`
* - **Operations**
  - {ref}`Upgrade <how_to_upgrade>`
  - {ref}`Route HTTP traffic to a non-charmed workload <how_to_haproxy_integrate_non_charm_workload>` | {ref}`Route TCP traffic to a non-charmed workload <how_to_haproxy_integrate_tcp_non_charm_workload>` | {ref}`Add HAProxy features to an ingress requirer <how_to_add_haproxy_features_to_ingress_requirer>` | {ref}`Load balance a gRPC server <how_to_haproxy_loadbalancing_grpc>`
  - {ref}`Add Kubernetes Gateway API features to an ingress requirer <how_to_add_gateway_api_features_to_ingress_requirer>` | {ref}`Route traffic for multiple workloads through a single Gateway <how_to_gateway_api_route_multiple_workloads>`
* - **Design**
  - {ref}`Modes of operation <explanation_modes_of_operation>`
  - {ref}`How haproxy-route-tcp works <explanation_haproxy_route_tcp>` | {ref}`The cache-config relation <reference_cache_config>`
  - {ref}`How gateway-route works <explanation_gateway_route>` | {ref}`The gateway-route relation <reference_gateway_route>`
```

## How this documentation is organized

This documentation uses the
[Diátaxis documentation structure](https://diataxis.fr/).

* The {ref}`Tutorial <tutorial_index>` takes you step-by-step through a basic deployment of the Ingress Configurator charm.
* The {ref}`How-to guides <how_to_index>` cover practical tasks for configuring, integrating, and maintaining your deployment.
* {ref}`Reference <reference_index>` provides technical details on the relation endpoints provided by this charm.
* {ref}`Explanation <explanation_index>` includes context and overviews on modes of operation and how the routing works.

## Project and community

The Ingress Configurator operator is a member of the Ubuntu family. It's an open-source project that warmly welcomes community 
projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/docs/ethos/code-of-conduct)
- [File a bug](https://github.com/canonical/ingress-configurator-operator/issues)
- Get support through the [Discourse forum](https://discourse.charmhub.io/)
- Join our [online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](https://github.com/canonical/ingress-configurator-operator/blob/main/CONTRIBUTING.md)

Thinking about using the Ingress Configurator operator for your next project? 
[Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

```{toctree}
:hidden:
tutorial/index.md
how-to/index.md
explanation/index.md
reference/index.md
release-notes/index.md
changelog.md
```
