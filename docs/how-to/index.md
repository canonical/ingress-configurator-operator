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

These guides apply regardless of the route-provider interface in use.

```{toctree}
:maxdepth: 1
Upgrade <upgrade.md>
```

## HAProxy

These guides apply to deployments using the `haproxy-route` or
`haproxy-route-tcp` interfaces.

```{toctree}
:maxdepth: 1
HAProxy guides <haproxy/index.md>
```

## Gateway API

These guides apply to deployments using the `gateway-route` interface.

```{toctree}
:maxdepth: 1
Gateway API guides <gateway-api/index.md>
```
