# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)


from stackstate_checks.agent_v2_integration_sample.agent_v2_integration_sample import agent_v2_integration_base
from stackstate_checks.base import AgentIntegrationInstance, HealthStream, HealthStreamUrn
from stackstate_checks.base.checks.v2.stateful_agent_check import StatefulAgentCheck
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

        # Persistent state updates after each check is run

        prstate_count = persistent_state.get("prstate_count")
        persistent_state["prstate_count"] = 1 if prstate_count is None else prstate_count + 1

        return CheckResponse(persistent_state=persistent_state)
