# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .__about__ import __version__
from .checks import AgentCheck, TopologyInstance, StackPackInstance, AgentIntegrationInstance, GeneratorAgentCheck,\
    StartSnapshot, StopSnapshot, Component, Relation, ServiceCheck
from .checks.openmetrics import OpenMetricsBaseCheck

from .config import is_affirmative
from .errors import ConfigurationError
from .utils.common import ensure_string, ensure_unicode, to_string
from .utils.identifiers import Identifiers
from .utils.telemetry import MetricStream, MetricHealthChecks, EventStream, EventHealthChecks, HealthState,\
    ServiceCheckStream, ServiceCheckHealthChecks, TopologyEventContext, SourceLink, Event
from .utils.health_api import Health, HealthStream, HealthStreamUrn, HealthType
from .utils.agent_integration_test_util import AgentIntegrationTestUtil
from .utils.persistent_state import StateDescriptor, StateManager, StateNotPersistedException, \
    StateCorruptedException, StateReadException

# Windows-only
try:
    from .checks.win import PDHBaseCheck
except ImportError:
    PDHBaseCheck = None

# Kubernetes dep will not always be installed
try:
    from .checks.kube_leader import KubeLeaderElectionBaseCheck
except ImportError:
    KubeLeaderElectionBaseCheck = None

__all__ = [
    '__version__',
    'AgentCheck',
    'TopologyInstance',
    'StackPackInstance',
    'AgentIntegrationInstance',
    'KubeLeaderElectionBaseCheck',
    'OpenMetricsBaseCheck',
    'PDHBaseCheck',
    'ConfigurationError',
    'ensure_string',
    'ensure_unicode',
    'is_affirmative',
    'to_string',
    'Identifiers',
    'MetricStream',
    'MetricHealthChecks',
    'EventStream',
    'EventHealthChecks',
    'HealthState',
    'ServiceCheckStream',
    'ServiceCheckHealthChecks',
    'AgentIntegrationTestUtil',
    'TopologyEventContext',
    'SourceLink',
    'Event',
    'StateDescriptor',
    'StateManager',
    'StateNotPersistedException',
    'StateCorruptedException',
    'StateReadException',
    'HealthStream',
    'Health',
    'HealthStreamUrn',
    'GeneratorAgentCheck',
    'StartSnapshot',
    'StopSnapshot',
    'Component',
    'Relation',
    'ServiceCheck'
]
