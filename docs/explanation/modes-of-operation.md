---
myst:
  html_meta:
    "description lang=en": "An explanation of the three modes of operation of the ingress-configurator charm: HAProxy integrator, HAProxy adapter, and gateway-route adapter."
---

(explanation_modes_of_operation)=

# Modes of operation

The `ingress-configurator` charm acts as a bridge between a route-provider charm
(such as `haproxy` or `gateway-api-integrator`) and the backend workloads that
need ingress. The charm always exposes the same `ingress` requirer interface to
backend applications, but the way it discovers backend addresses and ports — and
whether it propagates a proxied endpoint back to the backend — depends on the
**mode of operation**.

There are three modes, organised by the underlying route-provider interface and
the substrate (machine or Kubernetes):

| Mode | Substrate | Route-provider interface | Backend discovery |
|---|---|---|---|
| HAProxy integrator | Machine | `haproxy-route` | Charm configuration |
| HAProxy adapter | Machine | `haproxy-route` | `ingress` relation |
| Gateway-route adapter | Kubernetes | `gateway-route` | `ingress` relation |

## HAProxy integrator mode

In integrator mode, `ingress-configurator` is deployed without a direct
relation to the backend application. Instead, the operator provides the backend
address and port through charm configuration:

```
haproxy <-- haproxy-route -- ingress-configurator
                                (config: backend-addresses, backend-ports)
```

Because there is no `ingress` relation between `ingress-configurator` and the
backend, the proxied endpoint (the public URL assigned by HAProxy) is not
propagated back to the backend application.

This mode is suited to backends that are not managed by a Juju charm, or to
cases where the backend charm does not implement the `ingress` interface.
See {ref}`how_to_haproxy_integrate_non_charm_workload` for a worked example.

## HAProxy adapter mode

In adapter mode, `ingress-configurator` sits between HAProxy and a charmed
backend that implements the `ingress` requirer interface. The backend sends its
address and port to `ingress-configurator` over the `ingress` relation, and
`ingress-configurator` translates that information into `haproxy-route` relation
data:

```
haproxy <-- haproxy-route -- ingress-configurator <-- ingress -- backend-app
```

Because the `ingress` relation is present, `ingress-configurator` propagates the
proxied endpoint back to the backend application once HAProxy has assigned one.
The backend can then use that URL to advertise its public address.

This mode is suited to charmed backends that implement the `ingress` interface
but need access to HAProxy-specific features (such as TCP routing, custom
headers, or gRPC load balancing) that are not available through the standard
`ingress` interface alone. See {ref}`how_to_add_haproxy_features_to_ingress_requirer`
for a worked example.

## Gateway-route adapter mode

Gateway-route adapter mode is the Kubernetes equivalent of HAProxy adapter mode.
`ingress-configurator` receives backend address and port information over the
`ingress` relation and translates it into `gateway-route` relation data consumed
by `gateway-api-integrator`:

```
gateway-api-integrator <-- gateway-route -- ingress-configurator <-- ingress -- backend-app
```

As with HAProxy adapter mode, the proxied endpoint is propagated back to the
backend application.

### Port discovery and the dedicated-service fallback

`ingress-configurator` first attempts to route traffic to the ports that the
backend application has explicitly opened in Kubernetes. If the backend has not
opened any ports, `ingress-configurator` falls back to creating a dedicated
Kubernetes Service that uses the backend application's name as a label selector.

```{note}
The dedicated-service fallback requires that `ingress-configurator` is deployed
in the same Juju model as the backend application, so that the label selector can
match the backend's pods.
```

See {ref}`how_to_gateway_api_integrate_non_charm_workload` for a worked example
using a non-charmed backend, and
{ref}`how_to_gateway_api_add_features_to_ingress_requirer` for a charmed backend.
