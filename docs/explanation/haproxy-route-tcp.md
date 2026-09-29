---
myst:
  html_meta:
    "description lang=en": "Explanation of how the haproxy-route-tcp interface works in the Ingress Configurator charm, including architecture, Layer 4 routing, and key constraints."
---

(explanation_haproxy_route_tcp)=

# How haproxy-route-tcp works

The `haproxy-route-tcp` interface enables the `ingress-configurator` charm to manage
Layer 4 (TCP) load balancing and routing through the
[`haproxy`](https://charmhub.io/haproxy) charm. Unlike HTTP modes,
`haproxy-route-tcp` operates exclusively in **integrator TCP mode**, where
backend target addresses and port mappings are defined directly through charm
configuration rather than discovered via an `ingress` relation.

This interface is designed for TCP workloads where the backend is not a charmed application
or does not implement the `ingress` interface.

## Architecture

In TCP mode, `ingress-configurator` acts as a configuration translation layer for
Layer 4 traffic. The operator supplies backend IP addresses, port mappings, health
checks, and TLS parameters via charm configuration. `ingress-configurator` validates
this state and forwards the configuration over the `haproxy-route-tcp` relation.
HAProxy then opens the requested frontend listener ports and proxies raw TCP connections
to the backends.

```{mermaid}
flowchart LR
    Client(["External Client"]) --> HAProxy

    subgraph IC["ingress-configurator charm"]
        CONF["TCP Configs"]
    end

    subgraph HAProxy["haproxy charm"]
        FE["HAProxy TCP Frontend"]
    end

    subgraph Backend["TCP Backend Services"]
        BE1["Backend Instance 1"]
        BE2["Backend Instance 2"]
    end

    HAProxy --> BE1
    HAProxy --> BE2

    IC -- "haproxy-route-tcp relation" --> HAProxy

    classDef juju stroke:#1565c0,stroke-dasharray:5 5
    linkStyle 3 stroke:#1565c0,stroke-dasharray:5 5
```

## Traffic routing and port range mapping

The `tcp-port-mapping` option uses `frontend:backend` syntax:

- **Single port** (`<port>:<port>`): e.g. `"4000:20000"`
- **Port range** (`<start>-<end>:<start>-<end>`): e.g. `"4000-4005:20000-20005"`

```{note}
Single port mapping can also be configured using `tcp-backend-port` and `tcp-frontend-port`,
but these options are deprecated in favor of `tcp-port-mapping`.
```

## TLS and health checks

- **TLS termination and SNI**: Traffic can be decrypted at HAProxy before being sent to backends, or passed through. When TLS enforcement is active, SNI hostnames allow HAProxy to route encrypted TCP streams to the correct backend.
- **Layer 4 health checking**: HAProxy monitors backend availability before dispatching connections.
  Beyond simple TCP handshakes, HAProxy can perform generic send/expect string matching or utilize native protocol checks for databases.

## Constraints and limitations

- **Integrator mode only**: `haproxy-route-tcp` cannot be used with an `ingress` relation.
  The charm blocks if an `ingress` relation and `haproxy-route-tcp` are present simultaneously.
- **One route relation at a time**: The charm permits only one active route relation (`haproxy-route`, `haproxy-route-tcp`, or `gateway-route`).
- **No `cache-config` support**: The content-cache integration operates at Layer 7 and cannot be used alongside `haproxy-route-tcp`.
- **Substrate support**: `haproxy-route-tcp` is only supported on Machine substrates.
