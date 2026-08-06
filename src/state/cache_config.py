# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Cache-config relation state management module."""

import json
import logging
from typing import Optional, Self, cast

import ops
from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)

CACHE_CONFIG_RELATION_NAME = "cache-config"


@dataclass(frozen=True)
class CacheConfigState:
    """State for the cache-config relation.

    Attributes:
        proxy_cache_valid: Cache validity rule, e.g. "200 1h". None means not configured.
        healthcheck_interval: Health check interval in seconds, from charm config.
        healthcheck_path: Health check path, from charm config.
    """

    proxy_cache_valid: Optional[str]
    healthcheck_interval: Optional[int]
    healthcheck_path: Optional[str]

    @classmethod
    def build(cls, charm: ops.CharmBase) -> Self:
        """Build CacheConfigState from charm config.

        Args:
            charm: The ingress-configurator charm instance.

        Returns:
            CacheConfigState populated from charm config.
        """
        return cls(
            proxy_cache_valid=cast(Optional[str], charm.config.get("proxy-cache-valid")),
            healthcheck_interval=cast(Optional[int], charm.config.get("health-check-interval")),
            healthcheck_path=cast(Optional[str], charm.config.get("health-check-path")),
        )

    def to_relation_data(self, backends: list[str]) -> dict[str, str]:
        """Build the dict to write into the requirer app databag.

        Args:
            backends: List of backend URLs, e.g. ["http://10.0.0.1:8080"].

        Returns:
            Dict of string key/value pairs to write to the relation databag.
        """
        data: dict[str, str] = {
            "backends": json.dumps(backends),
            "healthcheck_interval": str((self.healthcheck_interval or 10) * 1000),
            "healthcheck_path": self.healthcheck_path or "/",
            "healthcheck_valid_status": json.dumps([200]),
        }
        if self.proxy_cache_valid is not None:
            data["proxy_cache_valid"] = json.dumps([self.proxy_cache_valid])
        return data

    @staticmethod
    def get_cache_backends(rel: ops.Relation) -> list[str] | None:
        """Read cache-backends from all content-cache unit databags.

        content-cache writes cache-backends as a JSON list to its own unit databag.
        An empty string sentinel means the relation was cleared.

        Args:
            rel: The cache-config relation.

        Returns:
            List of cache-backend URLs if available, None otherwise.
        """
        all_backends: list[str] = []
        for unit in rel.units:
            raw = rel.data[unit].get("cache-backends", "")
            if raw:
                all_backends.extend(json.loads(raw))
        return all_backends if all_backends else None
