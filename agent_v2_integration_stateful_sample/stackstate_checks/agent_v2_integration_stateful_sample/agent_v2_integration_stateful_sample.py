# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.agent_v2_integration_sample.agent_v2_integration_sample import agent_v2_integration_base
from stackstate_checks.base.checks.v2.stateful_agent_check import StatefulAgentCheck
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
        persistent_state = agent_v2_integration_stateful_base(self, persistent_state)

        return CheckResponse(persistent_state=persistent_state)


# Agent V2 integration stateful base that can be reused in the agent_v2_integration_transactional_sample
# base classes to retest the same functionality in the new base classes
def agent_v2_integration_stateful_base(self, persistent_state):
    self.log.info("Read or Write the 'persistent_counter' for this cycle.")
    self.log.info("Persistent State Received:")
    self.log.info(persistent_state)

    # Find the persistent state counter
    persistent_counter = persistent_state.get("persistent_counter")
    self.log.info("Found the 'persistent_counter' state: " + str(persistent_counter))

    # If the value exists then lets increase the value, if it does not the let's set a default
    if persistent_counter is not None and isinstance(persistent_counter, int):
        self.log.info("Found the 'persistent_counter' state: " + str(persistent_counter))
        persistent_state["persistent_counter"] = persistent_counter + 1
        self.log.info("Updating the the 'persistent_counter' state to: " + str(persistent_state["persistent_counter"]))
    else:
        self.log.info("The 'persistent_counter' state does not exist")
        persistent_state["persistent_counter"] = 1
        self.log.info("Writing '" + str(persistent_state["persistent_counter"]) + "' to the 'persistent_counter' state")

    return persistent_state
