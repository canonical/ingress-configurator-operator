---
myst:
  html_meta:
    "description lang=en": "How to use ingress-configurator to provide HAProxy features to charms that only implement the ingress relation."
---

(how_to_add_haproxy_features_to_ingress_requirer)=

# How to add HAProxy features to an ingress requirer charm

Charms that implement only the `ingress` relation can
leverage the additional features of the `haproxy-route` relation with the help
of the `ingress-configurator` charm.

## Deploy the charms

Deploy the ingress requirer charm:

```sh
juju deploy <ingress-requirer-charm>
```

If your charm has a separate action or configuration step to start the workload,
run it now and wait until the unit is `active`.

This guide assumes the ingress requirer charm already works correctly.

Deploy the `haproxy` and `self-signed-certificates` charms:

```sh
juju deploy haproxy --channel=2.8/edge --base=ubuntu@24.04
juju deploy self-signed-certificates 
juju integrate haproxy:certificates self-signed-certificates
```

Deploy the `ingress-configurator` charm:

```sh
juju deploy ingress-configurator --channel=edge
```

## Configure relations

Integrate the `ingress-configurator` charm with both the `haproxy` charm and the
ingress requirer:

```sh
juju integrate haproxy ingress-configurator
juju integrate ingress-configurator:ingress <ingress-requirer-charm>
```

Configure a hostname:

```sh
HOSTNAME=<hostname>
juju config ingress-configurator hostname=${HOSTNAME}
```

If `hostname` is not set, the endpoint hostname is provided by the
`haproxy-route` side.

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

### (Optional) Deny path-based routing

To prevent specific URL paths from being routed to the workload, configure `deny-paths`:

```sh
juju config ingress-configurator deny-paths=<path1>,<path2>
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

Get the HAProxy public IP address:

```sh
HAPROXY_IP=$(juju status --format=json | jq -r '.applications["haproxy"].units["haproxy/0"]."public-address"')
```

Use that IP address in a request with the configured hostname:

```sh
curl -i "https://${HAPROXY_IP}/" -H "Host: ${HOSTNAME}" --insecure
```

Adjust the path to match an endpoint exposed by your backend workload.

You should see a response from the backend workload, confirming that HAProxy is correctly routing traffic to it.
