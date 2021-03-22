# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

try:
    # Agent5 compatibility layer
    from checks import AgentCheck, AutoSnapshotMixin, StateFulMixin
    from checks.network_checks import NetworkCheck, Status, EventType
except ImportError:
    from .base import AgentCheck, AutoSnapshotMixin, StateFulMixin, TopologyInstance, StackPackInstance, AgentIntegrationInstance
    from .network import NetworkCheck, Status, EventType

__all__ = [
    'AgentCheck',
    'AutoSnapshotMixin',
    'StateFulMixin',
    'TopologyInstance',
    'StackPackInstance',
    'AgentIntegrationInstance',
    'NetworkCheck',
    'Status',
    'EventType',
]
