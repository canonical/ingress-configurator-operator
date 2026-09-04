---
myst:
  html_meta:
    "description lang=en": "Reference for the cache-config relation interface used by the Ingress Configurator charm, including databag fields."
---

(reference_cache_config)=

# The cache-config relation

The `cache-config` interface connects the Ingress Configurator charm (requirer) to the
[Content Cache](https://charmhub.io/content-cache) charm (provider). It configures the
Content Cache charm with backend origins, healthcheck parameters, and caching rules so
that HAProxy can route traffic through Content Cache.

## Databag fields

The Ingress Configurator charm writes the following fields to its **application databag**:

| Field | Type | Required | Description |
|---|---|---|---|
| `backends` | JSON array of strings | Yes | List of backend URLs (e.g. `["http://10.0.0.1:8080"]`) that content-cache should proxy. |
| `backend_hostname` | string | No | SNI hostname for backend TLS verification. Required when `backend-protocol` is `https`. content-cache passes this to nginx as `proxy_ssl_name`. When unset, the key is absent from the databag rather than present and empty. |
| `fail_timeout` | string | Yes | Time after which a backend is marked unavailable following a failure (e.g. `"30s"`). |
| `healthcheck_interval` | string | Yes | Healthcheck interval in milliseconds (e.g. `"10000"` for 10 s). |
| `healthcheck_path` | string | Yes | URL path used for healthchecks (e.g. `"/"`). |
| `healthcheck_valid_status` | JSON array of integers | Yes | HTTP status codes that indicate a healthy backend (e.g. `[200]`). |
| `healthcheck_ssl_verify` | JSON boolean | Yes | Whether nginx should verify the backend TLS certificate during healthchecks. |
| `proxy_cache_valid` | JSON array of strings | Yes | Cache validity rules in nginx format (e.g. `["200 1h"]`). An empty array emits no `proxy_cache_valid` directives, so caching defers to the backend's own `Cache-Control` and `Expires` headers. |

The Content Cache charm writes the following field to its **unit databag**:

| Field | Type | Description |
|---|---|---|
| `cache-backend` | string | URL on which Content Cache is reachable (e.g. `"https://10.1.0.5:30000"`). Ingress Configurator uses this to redirect HAProxy traffic through Content Cache. |
