# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2026-01-15

### Added

 - Add config options `tcp-retry-count`, `tcp-retry-redispatch`, `tcp-load-balancing-algorithm`, 
  `tcp-load-balancing-consistent-hashing`.
 - Fix bug where integrating with `haproxy-route-tcp` does not update the relationd data.

## 2026-01-12

### Added

 - Add external-grpc-port configuration to support gRPC traffic routing.

## 2025-11-25

### Added

 - Added upgrade documentation.

## 2025-08-01

### Changed

 - Add backend-protocol configuration option.

## 2025-07-21

### Changed

 - Require interval, fall and rise health checks to either be all set or none


## 2025-07-14

### Added

- Add check-interval, check-rise, check-fall, check-path and check-port configurations


## 2025-07-10

### Added

- Add retry-count, retry-interval and retry-redispatch configurations

1### Added

- Add ingress integration support


## 2025-07-09

### Added

- Add path and subdomain configuration to the `ingress-configurator` charm.
