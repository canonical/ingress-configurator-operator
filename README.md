# ingress-configurator-operator
<!-- Use this space for badges -->

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) that serves as a translation layer between the ingress interface and the haproxy-route interface. It provides more control on the haproxy-route interface through configurations including paths, subdomains and many more.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more.

For information about how to deploy, integrate, and manage this charm, see the Official [platform-engineering-charm-template Documentation](external link).

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
- backend_address
- backend_port

Apart from these, the ingress-configurator also supports a wide range of haproxy-route-related configurations:
- paths
- subdomains

To obtain the full list of configurations, see the official [CharmHub documentation](https://charmhub.io/ingress-configurator)

## (Optional) Integrations
<!-- Information about particularly relevant interfaces, endpoints or libraries related to the
charm. For example, peer relation endpoints required by other charms for integration.

Otherwise, include a link the Charmhub documentation on integrations.
--> 

## Learn more
<!-- 
Provide a list of resources, including the official documentation, developer documentation,
an official website for the software and a troubleshooting guide. Note that this list is not
exhaustive or always relevant for every charm. If there is no official troubleshooting guide,
include a link to the relevant Matrix channel.
-->

* [Read more]() <!--Link to the charm's official documentation-->
* [Developer documentation]() <!--Link to any developer documentation-->
* [Official webpage]() <!--(Optional) Link to official upstream webpage/blog/marketing content--> 
* [Troubleshooting]() <!--(Optional) Link to a page or section about troubleshooting/FAQ-->

## Project and community
* [Issues]() <!--Link to GitHub issues (if applicable)-->
* [Contributing]() <!--Link to any contribution guides--> 
* [Matrix]() <!--Link to contact info (if applicable), e.g. Matrix channel-->
* [Launchpad]() <!--Link to Launchpad (if applicable)-->

## (Optional) Licensing and trademark

