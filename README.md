# Ingress configurator operator
<!-- Use this space for badges -->

A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) that serves as a translation layer between the ingress interface and the haproxy-route interface. It provides more control on the haproxy-route interface through configurations including paths, subdomains and many more.

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
The ingress-configurator charm will be able to work both as an adapter and as an integrator. The integrator mode is used to support non-charm workloads that want to use the haproxy charm as a load balancer.
The following configurations must be configured for integrator mode:
- `backend_address`
- `backend_port`

Apart from these, the ingress-configurator also supports a wide range of haproxy-route-related configurations:
- paths
- subdomains

To obtain the full list of configurations, see the official [CharmHub documentation](https://charmhub.io/ingress-configurator).

## Learn more

* [Read more](https://charmhub.io/ingress-configurator) 
* [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) 

## Project and community
* [Issues](https://github.com/canonical/ingress-configurator-operator/issues) 
* [Contributing](CONTRIBUTING.md) 
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) 


