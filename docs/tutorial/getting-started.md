---
myst:
  html_meta:
    "description lang=en": "Step-by-step guide for deploying the Ingress Configurator charm to provide ingress to a backend Flask application running on Kubernetes."
---

(tutorial_getting_started)=

# Deploy the `ingress-configurator` charm with Gateway API

In this tutorial we'll deploy the `ingress-configurator` charm with `gateway-api-integrator` in Gateway API mode to provide ingress to a `flask-k8s` backend application running on Kubernetes.

(tutorial_requirements)=

## Requirements

You will need a working station, e.g., a laptop, with AMD64 architecture. Your working station
should have at least 4 CPU cores, 8 GB of RAM, and 50 GB of disk space.

<!-- SPREAD SKIP -->

````{tip}
You can use Multipass to create an isolated environment by running:
```
multipass launch 24.04 --name charm-tutorial-vm --cpus 4 --memory 8G --disk 50G
```
````

<!-- SPREAD SKIP END -->

This tutorial requires the following software to be installed on your working station
(either locally or in the Multipass VM):

- Juju 3.6
- Canonical Kubernetes

Use [Concierge](https://github.com/canonical/concierge) to set up Juju and Canonical Kubernetes:

```bash
sudo snap install --classic concierge
sudo concierge prepare -p k8s
```

The first command installs Concierge, and the second command uses Concierge to install
and configure Juju and Canonical Kubernetes with a Kubernetes controller.

## Set up a tutorial model

To manage resources effectively and to separate this tutorial's workload from your usual work, create a new model using the following command:

```bash
juju add-model ingress-tutorial
```

## Deploy the `gateway-api-integrator` charm

Deploy and configure the `gateway-api-integrator` charm. The `gateway-class` configuration must match your gateway controller's class name. For Canonical Kubernetes deployed via Concierge, this is `ck-gateway`:

```bash
juju deploy gateway-api-integrator
juju config gateway-api-integrator gateway-class=ck-gateway
```

## Configure TLS

Gateway API enforces HTTPS for secure traffic. Deploy a TLS provider and integrate it with the `gateway-api-integrator` charm:

```bash
juju deploy self-signed-certificates
juju integrate gateway-api-integrator:certificates self-signed-certificates
```

<!-- SPREAD
juju wait-for application gateway-api-integrator --query='status=="active"' --timeout 10m
-->

## Deploy the `ingress-configurator` charm

Deploy and configure the `ingress-configurator` charm. The `hostname` configuration specifies the domain name used to reach the backend, and `paths` defines the URL paths to route:

```bash
juju deploy ingress-configurator
juju config ingress-configurator hostname=flask.internal paths=/app
```

We use `flask.internal` as the hostname to match our sample Flask backend, and `/app` as the path where the Flask application serves content.

Integrate the `ingress-configurator` charm with the `gateway-api-integrator` charm:

```bash
juju integrate gateway-api-integrator:gateway-route ingress-configurator:gateway-route
```

## Deploy the backend application

For this tutorial we'll use the `flask-k8s` charm as a sample backend application:

```bash
juju deploy flask-k8s
```

Integrate the `flask-k8s` charm with `ingress-configurator`:

```bash
juju integrate flask-k8s:ingress ingress-configurator:ingress
```

## Verify the deployment

Now we can check the status of the model with `juju status --relations`. Wait until all units show `active` and `idle` status:

```bash
juju status --relations
```

Sample output:

```
Model             Controller  Cloud/Region        Version  SLA          Timestamp
ingress-tutorial  k8s         ck-gateway/default  3.6.0    unsupported  10:00:00Z

App                      Version  Status  Scale  Charm                    Channel  Rev  Address     Exposed  Message
flask-k8s                         active      1  flask-k8s                stable    14  10.0.0.1    no
gateway-api-integrator            active      1  gateway-api-integrator   stable    42  10.0.0.2    no
ingress-configurator              active      1  ingress-configurator     stable     7  10.0.0.3    no
self-signed-certificates          active      1  self-signed-certificates stable   156  10.0.0.4    no

Unit                        Workload  Agent  Address   Ports  Message
flask-k8s/0*                active    idle   10.1.0.1
gateway-api-integrator/0*   active    idle   10.1.0.2
ingress-configurator/0*     active    idle   10.1.0.3
self-signed-certificates/0* active    idle   10.1.0.4

Relation provider                          Requirer                               Interface        Type     Message
gateway-api-integrator:gateway-route       ingress-configurator:gateway-route     gateway-route    regular
gateway-api-integrator:certificates        self-signed-certificates:certificates  tls-certificates regular
ingress-configurator:ingress               flask-k8s:ingress                      ingress          regular
```

You should now be able to reach the `flask-k8s` charm using the gateway address and the hostname that you provided:

```bash
GATEWAY_IP=$(juju status --format json | jq -r '.applications."gateway-api-integrator".units."gateway-api-integrator/0"."public-address"')
curl -k --resolve flask.internal:443:$GATEWAY_IP https://flask.internal/app
```

A successful request returns the homepage of the `flask-k8s` charm:

```html
<h1>Welcome to flask-k8s Charm</h1>
```

## Clean up the environment

Well done! You've successfully provided ingress to a backend Flask application using `ingress-configurator` and `gateway-api-integrator`.

To remove the model environment you created, use the following command:

```bash
juju destroy-model ingress-tutorial --no-prompt
```

## Next steps

Check out these guides to learn more about configuring ingress for your applications:

- {ref}`Route HTTP traffic to a non-charmed workload with HAProxy <how_to_haproxy_integrate_non_charm_workload>`
- {ref}`Route TCP traffic to a non-charmed workload with HAProxy <how_to_haproxy_integrate_tcp_non_charm_workload>`
- {ref}`Add HAProxy features to an ingress requirer <how_to_add_haproxy_features_to_ingress_requirer>`
- {ref}`Load balance a gRPC server with HAProxy <how_to_haproxy_loadbalancing_grpc>`
- {ref}`how_to_upgrade`
