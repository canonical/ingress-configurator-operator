---
myst:
  html_meta:
    "description lang=en": "How to use ingress-configurator to provide HAProxy features to charms that only implement the ingress relation."
---

(how_to_add_haproxy_features_to_ingress_requirer)=
# How to add HAProxy features to an ingress requirer charm

This guide shows how a charm implementing only the `ingress` relation can
leverage the additional features of the `haproxy-route` relation with the help
of the `ingress-configurator` charm.

## Deploy an ingress requirer charm

Deploy an ingress requirer charm:

```sh
juju deploy <ingress-requirer-charm>
```

If your charm has a separate action or config step to start the workload,
run it now and wait until the unit is `active`.

This guide assumes the ingress requirer charm already works correctly. In this
case, `ingress-configurator` will expose the workload on the configured
`hostname` and any configured `additional-hostnames`. Optional path-based
routing is configured via `ingress-configurator`.

## Deploy and configure the `haproxy` charm

Deploy the `haproxy` and `self-signed-certificates` charms:

```sh
juju deploy haproxy --channel=2.8/edge --base=ubuntu@24.04
juju deploy self-signed-certificates 
juju integrate haproxy:certificates self-signed-certificates
```

## Deploy the `ingress-configurator` charm

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
