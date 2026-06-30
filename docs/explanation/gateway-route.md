---
myst:
  html_meta:
    "description lang=en": "Explanation of how the gateway-route interface works in the Ingress Configurator charm, including the architecture, data flow, and HTTPS modes."
---

(explanation_gateway_route)=

# How gateway-route works

The `gateway-route` interface is used together with the
[`gateway-api-integrator`](https://charmhub.io/gateway-api-integrator) charm,
which manages a Kubernetes [Gateway API](https://gateway-api.sigs.k8s.io/)
`Gateway` resource. The Ingress Configurator charm connects a workload that
only speaks the `ingress` relation to that `Gateway`, while also exposing
configuration options - such as `hostname` and `paths` - that can be tuned
without modifying either the workload or the `gateway-api-integrator`.

```{note}
The Gateway API is a Kubernetes-native concept, so the `gateway-route`
relation should only be used on a Kubernetes substrate. The charm must also be
deployed with `--trust` so it can manage Kubernetes resources.
```

## Architecture

How the backend `Service` is reached depends on whether the workload has
opened its port in Juju (see {ref}`Backend Service selection <explanation_backend_service_selection>`):

- **Port open**: the `HTTPRoute` forwards directly to the workload's own
  `Service`.
- **Port closed**: the Ingress Configurator creates an additional
  selector-based `Service` that targets the workload's pods, and the
  `HTTPRoute` forwards to that `Service`.

In the diagrams below, green arrows represent references between Kubernetes
resources (traffic/data flow) and blue dashed arrows represent Juju relations.
Charm units are shown as rounded nodes, while Kubernetes resources are shown
as rectangular nodes.

### Port open

```{mermaid}
flowchart LR
    CTRL(["Gateway controller"]) --> GW
    subgraph Workload["Workload charm"]
        WS["K8s: Workload Service"]
    end

    subgraph IC["ingress-configurator"]
        HR["K8s: HTTPRoute(s)"]
    end

    subgraph GAI["gateway-api-integrator"]
        GW["K8s: Gateway"]
        SEC["K8s: TLS Secret"]
        DNS["K8s: DNS Record"]
    end

    GW --> HR
    HR --> WS

    Workload -- "ingress relation" --> IC
    IC -- "gateway-route relation" --> GAI

    classDef k8s stroke:#2e7d32
    classDef juju stroke:#1565c0,stroke-dasharray:5 5
    linkStyle 0,1,2 stroke:#2e7d32
    linkStyle 3,4 stroke:#1565c0,stroke-dasharray:5 5
```

### Port closed

```{mermaid}
flowchart LR
    CTRL(["Gateway controller"]) --> GW
    subgraph Workload["Workload charm"]
        WS["K8s: Workload Service"]
    end

    subgraph IC["ingress-configurator"]
        HR["K8s: HTTPRoute(s)"]
        BS["K8s: Backend Service"]
    end

    subgraph GAI["gateway-api-integrator"]
        GW["K8s: Gateway"]
        SEC["K8s: TLS Secret"]
        DNS["K8s: DNS Record"]
    end

    GW --> HR
    HR --> BS
    BS --> WS

    Workload -- "ingress relation" --> IC
    IC -- "gateway-route relation" --> GAI

    classDef k8s stroke:#2e7d32
    classDef juju stroke:#1565c0,stroke-dasharray:5 5
    linkStyle 0,1,2,3 stroke:#2e7d32
    linkStyle 4,5 stroke:#1565c0,stroke-dasharray:5 5
```

## The gateway-route relation

The `gateway-route` interface is implemented by the
`charms.gateway_api_integrator.v1.gateway_route` library. It is a bidirectional
application databag exchange:

| Direction           | Fields                                                           | Description                                                                                                                                    |
|---------------------|------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| Requirer → Provider | `hostname`, `additional_hostnames`                               | The FQDN(s) the workload should be reachable on. Used by the provider to request TLS certificates and DNS records.                             |
| Provider → Requirer | `gateway_name`, `gateway_model`, `https_mode`, `gateway_address` | The identity of the `Gateway` resource so the requirer can build `HTTPRoute` `parentRefs`. `https_mode` tells the requirer how TLS is handled. |

The `https_mode` field is one of:

| Mode       | Meaning                                                        |
|------------|----------------------------------------------------------------|
| `disabled` | No TLS configured; only HTTP listeners exist on the `Gateway`. |
| `enabled`  | TLS configured; both HTTP and HTTPS listeners exist.           |
| `enforced` | TLS configured and HTTP is redirected to HTTPS.                |

```{note}
A single `gateway-api-integrator` can accept multiple `gateway-route`
relations, but each `ingress-configurator` instance is limited to one
`gateway-route` relation. To route traffic for multiple workloads through the
same `Gateway`, deploy a separate `ingress-configurator` for each workload and
relate them all to the same `gateway-api-integrator`.
```

## How HTTPRoute resources are created

The Ingress Configurator builds `HTTPRoute` resources based on the
`https_mode` received from the provider and the hostname(s) from its own
configuration:

- **One HTTP route** is always created. It covers all hostnames and attaches
  to every per-hostname HTTP listener on the `Gateway` via multiple
  `parentRefs`. When no hostnames are configured, it falls back to the
  `Gateway`'s hostname-less HTTP listener.
- When `https_mode` is **`enabled`** or **`enforced`**, **one HTTPS route per
  hostname** is created, each attaching to its corresponding per-hostname HTTPS
  listener.
- When `https_mode` is **`enforced`**, the HTTP route does **not** forward to
  the backend. Instead it issues a `301` HTTPS redirect using a
  `RequestRedirect` filter.

(explanation_backend_service_selection)=

## Backend Service selection

The `HTTPRoute` forwards traffic to a Kubernetes `Service`. Which `Service` is
used depends on whether the workload charm has opened its port in Juju:

- **Port is open**: the workload's own `Service` is referenced directly by the
  `HTTPRoute`'s `backendRefs`.
- **Port is not open**: the Ingress Configurator creates a selector-based
  `Service` that targets the workload's pods by the
  `app.kubernetes.io/name` label. This allows routing even when the workload
  has not declared its port to Juju.

All resources created by the Ingress Configurator are labelled with
`ingress-configurator.charm.juju.is/managed-by` so they can be discovered and
cleaned up on relation departure.

## Constraints and limitations

- **Kubernetes only**: the Gateway API is a Kubernetes-native concept, so the
  `gateway-route` relation should only be used on a Kubernetes substrate.
- **HTTP backend protocol only**: the `backend-protocol` configuration option
  only accepts `http` with `gateway-route`. TLS termination happens at the
  `Gateway`, not at the backend.
- **One route relation at a time**: the charm blocks if more than one of
  `haproxy-route`, `haproxy-route-tcp`, or `gateway-route` is related
  simultaneously.
- **`--trust` required**: the charm needs Kubernetes RBAC permissions to
  manage `HTTPRoute` and `Service` resources.
