---
myst:
  html_meta:
    "description lang=en": "How to route TCP traffic to a non-charmed workload using ingress-configurator and HAProxy."
---

(how_to_haproxy_integrate_tcp_non_charm_workload)=

# How to route TCP traffic to a non-charmed workload through HAProxy

You can use the `ingress-configurator` charm to route raw TCP
traffic from HAProxy to a backend that is not managed by a Juju charm.

Use this approach for protocols other than HTTP/HTTPS/gRPC (for example SSH,
SMTP, or PostgreSQL), or when you want HAProxy to pass HTTP/HTTPS/gRPC traffic
through to the backend without any inspection.

## Prerequisites

Ensure your backend application is running and reachable from the Juju model.
Set its IP address in a variable:

```sh
BACKEND_IP=<backend-ip>
```

```{note}
`tcp-backend-addresses` accepts IP addresses only, not FQDNs.
```

Deploy the `haproxy` and `self-signed-certificates` charms:

```sh
juju deploy haproxy --channel=2.8/edge --base=ubuntu@24.04
juju deploy self-signed-certificates
juju integrate haproxy:certificates self-signed-certificates
```

## Deploy and integrate the `ingress-configurator` charm

```sh
juju deploy ingress-configurator --channel=edge
juju integrate haproxy:haproxy-route-tcp ingress-configurator:haproxy-route-tcp
```

## Configure the backend

Set the backend address, the backend port, the HAProxy frontend port, and TLS
options. For example, to relay SMTP traffic:

```sh
juju config ingress-configurator \
  tcp-backend-addresses=$BACKEND_IP \
  tcp-backend-port=587 \
  tcp-frontend-port=587 \
  tcp-enforce-tls=false
```

## Verify that the backend is reachable through HAProxy

Get the HAProxy public IP address:

```sh
HAPROXY_IP=$(juju status --format=json | jq -r '.applications["haproxy"].units["haproxy/0"]."public-address"')
```

Test the connection on the configured frontend port:

```sh
nc -zv $HAPROXY_IP 587
```

You should see a successful connection, confirming that HAProxy is correctly routing traffic to the backend.
