---
myst:
  html_meta:
    "description lang=en": "How to route HTTP traffic to a non-charmed workload using ingress-configurator on Kubernetes Gateway API."
---

(how_to_gateway_api_integrate_non_charm_workload)=

# How to route HTTP traffic to a non-charmed workload through Kubernetes Gateway API

You can use the `ingress-configurator` charm to route traffic from a Kubernetes
Gateway API to a backend application that is not managed by a Juju charm.

## Prerequisites

Deploy the `gateway-api-integrator` charm:

```sh
juju deploy gateway-api-integrator --channel=latest/edge --trust
```

Ensure you have a backend workload running and accessible from the Juju model.
Set its IP address in a variable:

```{note}
`backend-addresses` accepts IP addresses only (IPv4 and IPv6), not FQDNs.
```

```sh
BACKEND_IP=<backend-ip>
```

Verify the backend is responding:

```sh
curl http://${BACKEND_IP}/ -I
```

Adjust the path to match an endpoint exposed by your backend workload.

You should see a successful HTTP response from the backend.

## Deploy the `ingress-configurator` charm

```sh
juju deploy ingress-configurator --channel=edge --trust
```

The `--trust` flag is required to allow `ingress-configurator` to manage
Kubernetes resources in the cluster.

## Configure the `ingress-configurator` charm

Integrate the `ingress-configurator` charm with the `gateway-api-integrator` charm:

```sh
juju integrate ingress-configurator:gateway-route gateway-api-integrator
```

Configure the backend address, port, and hostname:

```sh
HOSTNAME=<hostname>
juju config ingress-configurator \
  backend-addresses=${BACKEND_IP} \
  backend-ports=<backend-port> \
  hostname=${HOSTNAME}
```

```{note}
`backend-protocol=https` is not supported for Gateway API. TLS termination is
managed by the gateway itself.
```

### (Optional) Configure additional hostnames

To expose the workload on additional hostnames, configure `additional-hostnames`:

```sh
juju config ingress-configurator additional-hostnames=<hostname1>,<hostname2>
```

### (Optional) Configure path-based routing

To restrict routing to specific URL paths, configure `paths`:

```sh
juju config ingress-configurator paths=<path1>,<path2>
```

## Verify that the backend is reachable through the gateway

Run the `get-proxied-endpoints` action on `ingress-configurator`:

```sh
juju run ingress-configurator/leader get-proxied-endpoints
```

You should see `https://${HOSTNAME}/` in the `endpoints` field.

Use the endpoint URL from the `endpoints` field to send a request to the backend:

```sh
curl -i "<endpoint-url>" --insecure
```

Adjust the path to match an endpoint exposed by your backend workload.

You should see a response from the backend workload, confirming that the gateway
is correctly routing traffic to it.
