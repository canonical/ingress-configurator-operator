---
myst:
  html_meta:
    "description lang=en": "Reference for the gateway-route relation interface used by the Ingress Configurator charm, including databag fields and https_mode values."
---

(reference_gateway_route)=

# The gateway-route relation

The `gateway-route` interface is implemented by the
`charms.gateway_api_integrator.v1.gateway_route` library. It is a bidirectional
application databag exchange:

| Direction           | Fields                                                           | Description                                                                                                                                    |
|---------------------|------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| Requirer → Provider | `hostname`, `additional_hostnames`                               | The FQDN(s) the workload should be reachable on. Used by the provider to request TLS certificates and DNS records.                             |
| Provider → Requirer | `gateway_name`, `gateway_model`, `https_mode`, `gateway_address` | The identity of the `Gateway` resource so the requirer can build `HTTPRoute` `parentRefs`. |

The `https_mode` field tells the requirer how TLS is handled. The field has three available modes:

| Mode       | Meaning                                                        |
|------------|----------------------------------------------------------------|
| `disabled` | No TLS configured; only HTTP listeners exist on the `Gateway`. |
| `enabled`  | TLS configured; both HTTP and HTTPS listeners exist.           |
| `enforced` | TLS configured and HTTP is redirected to HTTPS.                |
