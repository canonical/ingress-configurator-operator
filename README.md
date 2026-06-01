# Ingress configurator operator
<!-- Use this space for badges -->

A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) that serves as a translation layer between the ingress interface and route-provider interfaces.

It currently supports:

- `haproxy-route` and `haproxy-route-tcp`
- `gateway-route` (adapter mode on Kubernetes)

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more.

For information about how to deploy, integrate, and manage this charm, see the Official [Ingress configurator operator documentation](https://charmhub.io/ingress-configurator).

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
The ingress-configurator charm supports adapter mode and integrator mode.

- Adapter mode: a workload charm relates over `ingress`, and ingress-configurator forwards requirements to a route provider.
- Integrator mode: non-charm workloads are described by config and routed through route-provider relations The following configurations must be configured:
  - `backend-addresses`
  - `backend-ports`

#### HAProxy

Supported through `haproxy-route` or `haproxy-route-tcp` relations.

- Supports both adapter and integrator workflows.
- Supports a broad set of haproxy-route related configurations:
  - paths
  - subdomains

#### Gateway API

Supported through the `gateway-route` relation.

- Supports only adapter mode.
- Requires that the backend related through `ingress` has opened its ports.
- `https` option for `backend-protocol` is not supported.

To obtain the full list of configurations, see the official [CharmHub documentation](https://charmhub.io/ingress-configurator).

## Learn more

- [Read more](https://charmhub.io/ingress-configurator)
- [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Project and community

- [Issues](https://github.com/canonical/ingress-configurator-operator/issues)
- [Contributing](CONTRIBUTING.md)
- [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
