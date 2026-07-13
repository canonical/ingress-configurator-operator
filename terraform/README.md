# Terraform module for ingress-configurator

This is a [Terraform](https://www.terraform.io/) module that deploys the
[ingress-configurator](https://charmhub.io/ingress-configurator) charm using the
[Juju provider](https://registry.terraform.io/providers/juju/juju/latest).

The module is a Charm module as defined by CC008 (Charm Terraform Standards): it
deploys a single charm and is intended to be consumed by higher-level component,
product, or deployment modules.

## Requirements

- Terraform `~> 1.12`
- Juju provider `>= 1.0.0`

## Usage

```hcl
module "ingress_configurator" {
  source     = "path/to/this/module"
  model_uuid = juju_model.this.uuid
}
```

## Inputs

| Name          | Type          | Default                  | Nullable | Description                                                                 |
| ------------- | ------------- | ------------------------ | -------- | --------------------------------------------------------------------------- |
| `app_name`    | `string`      | `"ingress-configurator"` | yes      | Name of the application in the Juju model.                                  |
| `base`        | `string`      | `"ubuntu@24.04"`         | yes      | The operating system on which to deploy.                                    |
| `channel`     | `string`      | `"latest/stable"`        | no       | The channel to use when deploying the charm.                                |
| `config`      | `map(string)` | `{}`                     | yes      | Application config. See the [charm configuration options][config].          |
| `constraints` | `string`      | `null`                   | yes      | Juju constraints to apply for this application.                             |
| `model_uuid`  | `string`      | n/a (required)           | no       | UUID of the Juju model where the application will be deployed.              |
| `revision`    | `number`      | `null`                   | yes      | Revision number of the charm. `null` deploys the latest on the channel.     |
| `trust`       | `bool`        | `false`                  | yes      | Deploy with `--trust` (required for Kubernetes).                            |
| `units`       | `number`      | `1`                      | yes      | Number of units to deploy.                                                  |

[config]: https://charmhub.io/ingress-configurator/configurations

## Outputs

| Name          | Type     | Description                                                                                   |
| ------------- | -------- | --------------------------------------------------------------------------------------------- |
| `application` | `object` | The deployed `juju_application` resource.                                                     |
| `provides`    | `object` | Map of the provided integration endpoints. Each entry has `kind`, `name`, and `endpoint`.     |
| `requires`    | `object` | Map of the required integration endpoints. Each entry has `kind`, `name`, and `endpoint`.     |

### `provides`

| Key       | Endpoint  | Interface |
| --------- | --------- | --------- |
| `ingress` | `ingress` | `ingress` |

### `requires`

| Key                 | Endpoint            | Interface           |
| ------------------- | ------------------- | ------------------- |
| `gateway_route`     | `gateway-route`     | `gateway-route`     |
| `haproxy_route`     | `haproxy-route`     | `haproxy-route`     |
| `haproxy_route_tcp` | `haproxy-route-tcp` | `haproxy-route-tcp` |
