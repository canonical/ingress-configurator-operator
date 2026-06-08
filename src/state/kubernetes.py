# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Kubernetes-specific state for the ingress-configurator-operator."""

from typing import Annotated

from annotated_types import Len
from pydantic import Field
from pydantic.dataclasses import dataclass
from pydantic.networks import IPvAnyAddress


@dataclass(frozen=True)
class NodePortState:
    """Data returned from the Kubernetes API for a NodePort service.

    Attributes:
        backend_addresses: Addresses of worker nodes in the cluster.
        backend_port: The nodePort allocated by Kubernetes.
        service_name: The name of the NodePort service.
    """

    backend_addresses: Annotated[list[IPvAnyAddress], Len(min_length=1)]
    backend_port: Annotated[int, Field(gt=0, le=65535)]
    service_name: str
