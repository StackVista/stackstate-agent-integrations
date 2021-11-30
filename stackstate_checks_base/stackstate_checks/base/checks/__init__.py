# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

try:
    # Agent5 compatibility layer
    from checks import AgentCheck
    from checks.network_checks import NetworkCheck, Status, EventType
except ImportError:
    from .base import AgentCheck, TopologyInstance, StackPackInstance, AgentIntegrationInstance,\
        HealthStream, HealthStreamUrn, Health
    from .network import NetworkCheck, Status, EventType
    from .generator import GeneratorAgentCheck, StartSnapshot, StopSnapshot, Component, Relation, ServiceCheck
__all__ = [
    'AgentCheck',
    'TopologyInstance',
    'StackPackInstance',
    'AgentIntegrationInstance',
    'NetworkCheck',
    'Status',
    'EventType',
    'HealthStream',
    'HealthStreamUrn',
    'Health',
    'GeneratorAgentCheck',
    'StartSnapshot',
    'StopSnapshot',
    'Component',
    'Relation',
    'ServiceCheck'
]
