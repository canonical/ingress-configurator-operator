# Ingress configurator operator
<!-- Use this space for badges -->

A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) that serves as a translation layer between the ingress interface and route-provider interfaces.

It currently supports:

- `haproxy-route` and `haproxy-route-tcp`
- `gateway-route` (adapter mode on Kubernetes)

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more.

For information about how to deploy, integrate, and manage this charm, see the Official [Ingress configurator operator documentation](https://canonical.com/juju/docs/ingress-configurator-charm/latest/).

## Get started
<!--If the charm already contains a relevant how-to guide or tutorial in its documentation,
use this section to link the documentation. You don’t need to duplicate documentation here.
If the tutorial is more complex than getting started, then provide brief descriptions of the
steps needed for the simplest possible deployment. Make sure to include software and hardware
prerequisites.

This section could be structured in the following way:

### Set up
<Steps for setting up the environment (e.g. via Multipass)>

### Deploy
<Steps for deploying the charm>

-->

### Basic operations
<!--Brief walkthrough of performing standard configurations or operations.

Use this section to provide information on important actions, required configurations, or
other operations the user should know about. You don’t need to list every action or configuration.
Use this section to link the Charmhub documentation for actions and configurations.

You may also want to link to the `charmcraft.yaml` file here.
-->
The ingress-configurator charm supports two workflows.

- **Ingress relation workflow**: a workload charm relates over `ingress`, and ingress-configurator forwards the routing requirements to a route provider.
- **Config-driven workflow**: non-charm workloads are described by config and routed through route-provider relations.
  The following configurations must be set:
  - `backend-addresses`
  - `backend-ports`

#### HAProxy

HAProxy is supported through the `haproxy-route` or the `haproxy-route-tcp` relation.

- `haproxy-route` supports both the ingress relation and config-driven workflows.
- `haproxy-route-tcp` supports the config-driven workflow only.
- Supports a broad set of haproxy-route related configurations:
  - paths
  - subdomains

#### Gateway API

Gateway API is supported through the `gateway-route` relation.

- Supports the ingress relation workflow only; config-driven backends are not supported.
- Requires that the backend related through `ingress` has opened its ports.
- `https` option for `backend-protocol` is not supported.

#### Content-cache (optional)

The `cache-config` relation integrates with [content-cache](https://charmhub.io/content-cache)
to route haproxy traffic through a caching layer instead of directly to the real backend.

```
juju integrate ingress-configurator content-cache
```

When the relation is present:

1. ingress-configurator sends the resolved backend addresses and healthcheck config to content-cache.
2. content-cache returns its own IP and port as `cache-backend` (a plain URL string in its unit databag).
3. ingress-configurator configures haproxy to use the content-cache address as the backend.

When the relation is removed, haproxy reverts to the original backend addresses.

**Limitations:**

- Only supported with `haproxy-route` (HTTP/HTTPS backends).
- Not supported with `haproxy-route-tcp` (TCP) or `gateway-route` (gRPC).

**Optional configuration:**

- `cache-proxy-cache-valid`: Cache validity rule sent to content-cache, for example `"200 1h"`.
- `cache-fail-timeout`: Time before marking a backend unavailable after a failed health check, for example `"30s"`.
- `cache-healthcheck-ssl-verify`: Whether content-cache verifies backend TLS certificates during health checks.

To obtain the full list of configurations, see the official [CharmHub documentation](https://charmhub.io/ingress-configurator).

## Learn more

- [Read more](https://charmhub.io/ingress-configurator)
- [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Project and community

- [Issues](https://github.com/canonical/ingress-configurator-operator/issues)
- [Contributing](CONTRIBUTING.md)
- [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
