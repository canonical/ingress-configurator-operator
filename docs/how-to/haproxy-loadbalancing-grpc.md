---
myst:
  html_meta:
    "description lang=en": "How to use ingress-configurator to load balance a gRPC server through HAProxy."
---

(how_to_haproxy_loadbalancing_grpc)=

# How to load balance a gRPC server through HAProxy

This guide shows how to configure the `ingress-configurator` charm to expose a
gRPC backend through HAProxy.

gRPC load balancing requires the backend to support HTTP/2 over TLS. HAProxy
routes gRPC traffic through port 443 by default, or through a dedicated frontend
port configured via `external-grpc-port`.

## Prerequisites

- A HAProxy deployment with TLS configured. See the
  [HAProxy getting started tutorial](https://charmhub.io/haproxy/docs) for setup
  instructions.
- A gRPC backend reachable from the Juju model with TLS enabled. See the HAProxy
  operator's
  [gRPC load balancing guide](https://canonical-haproxy-operator.readthedocs-hosted.com/en/latest/how-to/loadbalancing-for-a-grpc-server.html)
  for instructions on setting up a gRPC backend (the `flagd` section).

## Deploy the `ingress-configurator` charm

```sh
juju deploy ingress-configurator grpc-configurator --channel=latest/edge
```

## Configure the charm

Set the backend address, port, protocol, and hostname. The `backend-protocol`
must be `https` for gRPC backends:

```sh
GRPC_SERVER_ADDRESS=<backend-ip>
juju config grpc-configurator \
    backend-addresses=$GRPC_SERVER_ADDRESS \
    backend-ports=<backend-port> \
    backend-protocol=https \
    hostname=<grpc-hostname>
```

If you want gRPC traffic on a dedicated frontend port rather than port 443, also
set `external-grpc-port`:

```sh
juju config grpc-configurator external-grpc-port=<port>
```

## Integrate with HAProxy

```sh
juju integrate grpc-configurator:haproxy-route haproxy
```

## Verify the connection

Once all charms are active, verify the gRPC server is reachable through HAProxy:

```sh
HAPROXY_IP=$(juju status --format json | jq -r '.applications.haproxy.units."haproxy/0"."public-address"')
grpcurl -insecure -d '{}' <grpc-hostname>:<port> <service-method>
```
