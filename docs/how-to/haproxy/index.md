---
myst:
  html_meta:
    "description lang=en": "How-to guides for using ingress-configurator with HAProxy."
---

(how_to_haproxy_index)=

# HAProxy guides

Guides for deployments where `ingress-configurator` provides ingress through the
`haproxy-route` or `haproxy-route-tcp` interfaces.

```{toctree}
:maxdepth: 1
Route HTTP traffic to a non-charmed workload <integrate-non-charm-workload.md>
Route TCP traffic to a non-charmed workload <integrate-tcp-non-charm-workload.md>
Add HAProxy features to an ingress requirer <add-features-to-ingress-requirer.md>
Load balance a gRPC server <loadbalancing-grpc.md>
```
