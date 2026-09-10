# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2026-09-10

### Added

- `ingress-per-unit` provider endpoint (interface `ingress_per_unit`). When related
  together with `gateway-route`, each requirer unit gets its own URL
  (`/<model>-<unit_name>`), backed by a per-unit Kubernetes `Service` (pod-name
  selector) and `HTTPRoute`. Kubernetes only; the requirer must be deployed in the
  same model as ingress-configurator; mutually exclusive with the `ingress`,
  `haproxy-route`, and `haproxy-route-tcp` relations.
