---
myst:
  html_meta:
    "description lang=en": "How to route HTTP traffic to a non-charmed workload using ingress-configurator and HAProxy."
---

(how_to_haproxy_integrate_non_charm_workload)=
# How to route HTTP traffic to non-charmed workloads with HAProxy

This guide shows how to use the `ingress-configurator` charm to route traffic
from HAProxy to a backend application that is not managed by a Juju charm.

## Prerequisites

Deploy the `haproxy` and `self-signed-certificates` charms:

```sh
juju deploy haproxy --channel=2.8/edge --base=ubuntu@24.04
juju deploy self-signed-certificates cert
juju integrate haproxy:certificates cert
```

## Deploy the `ingress-configurator` charm

```sh
juju deploy ingress-configurator --channel=edge
```

## Confirm the backend is reachable

This guide assumes you already have a backend workload running and accessible
from the Juju model. Set its IP address in a variable (note: `backend-addresses`
accepts IP addresses only, not FQDNs):

```sh
BACKEND_IP=<backend-ip>
```

Verify the backend is responding before configuring HAProxy:

```sh
curl http://${BACKEND_IP} -I
```

You should see a successful HTTP response from the backend.

## Configure the `ingress-configurator` charm

Integrate the `ingress-configurator` charm with the `haproxy` charm:

```sh
juju integrate haproxy ingress-configurator
```

Configure the backend address, port, and hostname:

```sh
HOSTNAME=<hostname>
juju config ingress-configurator \
  backend-addresses=${BACKEND_IP} \
  backend-ports=<backend-port> \
  hostname=${HOSTNAME}
```

## Verify that the backend is reachable through HAProxy

Get the HAProxy public IP address:

```sh
HAPROXY_IP=$(juju status --format=json | jq -r '.applications["haproxy"].units["haproxy/0"]."public-address"')
```

Send a request using the configured hostname:

```sh
curl -i "https://${HAPROXY_IP}/" --insecure -H "Host: ${HOSTNAME}"
```

You should see a successful response from the backend.
