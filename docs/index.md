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

```{toctree}
:hidden:
how-to/index.md
changelog.md
```
