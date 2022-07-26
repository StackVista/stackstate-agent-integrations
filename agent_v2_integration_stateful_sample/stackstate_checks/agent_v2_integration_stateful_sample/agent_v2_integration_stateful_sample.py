# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.agent_v2_integration_sample.agent_v2_integration_sample import agent_v2_integration_base
from stackstate_checks.base.checks.v2.stateful_agent_check import StatefulAgentCheck
from stackstate_checks.base.checks.v2.types import StateType
from stackstate_checks.base import AgentIntegrationInstance, HealthStream, HealthStreamUrn
from stackstate_checks.checks import CheckResponse
from random import seed

seed(1)


class AgentIntegrationSampleStatefulCheck(StatefulAgentCheck):
    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn("agent-v2-integration-stateful-sample", "sample"))

    def get_instance_key(self, instance):
        return AgentIntegrationInstance("agent-v2-integration-stateful", "sample")

    def stateful_check(self, instance, persistent_state):
        agent_v2_integration_base(self, instance, "agent-v2-integration-stateful-sample")
        persistent_state = agent_v2_integration_stateful_base(persistent_state)

        return CheckResponse(persistent_state=persistent_state)


# Agent V2 integration stateful base that can be reused in the agent_v2_integration_transactional_sample
# base classes to retest the same functionality in the new base classes
def agent_v2_integration_stateful_base(persistent_state):  # type: (StateType) -> StateType
    # Add counter in persistent state that updates after each check is run
    persistent_counter = persistent_state.get("persistent_counter")
    persistent_state["persistent_counter"] = 1 if persistent_counter is None else persistent_counter + 1

    return persistent_state
