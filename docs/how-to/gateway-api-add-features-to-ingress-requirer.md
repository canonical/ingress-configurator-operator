---
myst:
  html_meta:
    "description lang=en": "How to use ingress-configurator to provide Kubernetes Gateway API features to charms that only implement the ingress relation."
---

(how_to_add_gateway_api_features_to_ingress_requirer)=

# How to add Kubernetes Gateway API features to an ingress requirer charm

Charms that implement only the `ingress` relation can leverage the Kubernetes
Gateway API with the help of the `ingress-configurator` charm.

## Deploy the charms

Deploy the ingress requirer charm:

```sh
juju deploy <ingress-requirer-charm>
```

If your charm has a separate action or configuration step to start the workload,
run it now and wait until the unit is `active`.

This guide assumes the ingress requirer charm already works correctly.

Deploy the `gateway-api-integrator` charm:

```sh
juju deploy gateway-api-integrator --channel=latest/edge --trust
```

Deploy the `ingress-configurator` charm:

```sh
juju deploy ingress-configurator --channel=edge --trust
```

The `--trust` flag is required to allow `ingress-configurator` to manage
Kubernetes resources in the cluster.

## Configure relations

Integrate the `ingress-configurator` charm with both the `gateway-api-integrator`
charm and the ingress requirer:

```sh
juju integrate ingress-configurator:gateway-route gateway-api-integrator
juju integrate ingress-configurator:ingress <ingress-requirer-charm>
```

Configure a hostname:

```sh
HOSTNAME=<hostname>
juju config ingress-configurator hostname=${HOSTNAME}
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

## Verify proxied endpoints

Use the `get-proxied-endpoints` action on `ingress-configurator`:

```sh
juju run ingress-configurator/leader get-proxied-endpoints
```

You should see `https://${HOSTNAME}/` in the `endpoints` field.

If `additional-hostnames` is configured, those hostnames should also appear in
the `endpoints` field.

## Verify routing with curl

Use the endpoint URL from the `endpoints` field to send a request to the backend:

```sh
curl -i "<endpoint-url>" --insecure
```

Adjust the path to match an endpoint exposed by your backend workload.

You should see a response from the backend workload, confirming that the gateway
is correctly routing traffic to it.
