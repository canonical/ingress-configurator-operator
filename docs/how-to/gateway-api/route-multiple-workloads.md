---
myst:
  html_meta:
    "description lang=en": "Learn how to route traffic for multiple workloads through a single Gateway using ingress-configurator and gateway-api-integrator."
---

(how_to_gateway_api_route_multiple_workloads)=

# How to route traffic for multiple workloads through a single Gateway

The `gateway-api-integrator` charm manages a single Kubernetes `Gateway` resource and accepts multiple `gateway-route` relations.
Each`ingress-configurator` instance handles exactly one workload,
so to route traffic for multiple workloads through the same `Gateway`,
deploy one `ingress-configurator` per workload and integrate them all to the same `gateway-api-integrator` instance.

This guide assumes you already have `gateway-api-integrator` deployed and configured.
If not, begin by following {ref}`how_to_add_gateway_api_features_to_ingress_requirer`.

## Deploy ingress-configurator for each workload

For each ingress requirer charm,
deploy a dedicated `ingress-configurator` instance and give each a unique application name:

```sh
juju deploy ingress-configurator --channel=latest/stable --trust ingress-configurator-a
juju deploy ingress-configurator --channel=latest/stable --trust ingress-configurator-b
```

## Configure relations

Integrate each `ingress-configurator` to `gateway-api-integrator` and to its
corresponding workload:

```sh
juju integrate ingress-configurator-a:gateway-route gateway-api-integrator
juju integrate ingress-configurator-a:ingress <workload-charm-a>

juju integrate ingress-configurator-b:gateway-route gateway-api-integrator
juju integrate ingress-configurator-b:ingress <workload-charm-b>
```

Configure a distinct hostname for each instance:

```sh
juju config ingress-configurator-a hostname=<hostname-a>
juju config ingress-configurator-b hostname=<hostname-b>
```

Each `ingress-configurator` will create its own `HTTPRoute` resources
pointing to its respective workload, all sharing the same `Gateway`.
