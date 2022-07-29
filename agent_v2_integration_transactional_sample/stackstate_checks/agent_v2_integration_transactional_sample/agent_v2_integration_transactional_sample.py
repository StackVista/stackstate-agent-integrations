# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.agent_v2_integration_stateful_sample.agent_v2_integration_stateful_sample \
    import agent_v2_integration_stateful_base
from stackstate_checks.agent_v2_integration_sample.agent_v2_integration_sample import agent_v2_integration_base
from stackstate_checks.base.checks.v2.transactional_agent_check import TransactionalAgentCheck
from stackstate_checks.base import AgentIntegrationInstance, HealthStream, HealthStreamUrn
from stackstate_checks.checks import CheckResponse
from random import seed

seed(1)


class AgentV2IntegrationTransactionalSampleCheck(TransactionalAgentCheck):
    test = 0

    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn("agent-v2-integration-transactional-sample", "sample"))

    def get_instance_key(self, instance):
        return AgentIntegrationInstance("agent-v2-integration-transactional", "sample")

    def transactional_check(self, instance, transactional_state, persistent_state):
        self.test = self.test + 1
        self.log.info("Test value is increase to: " + str(self.test))

        agent_v2_integration_base(self, instance, "agent-v2-integration-transactional-sample")
        persistent_state = agent_v2_integration_stateful_base(self, persistent_state)

        self.log.info("Read or Write the 'transaction_counter' for this cycle.")

        # Find the persistent state counter
        transaction_counter = transactional_state.get("transaction_counter")

        # If the value exists then lets increase the value, if it does not the let's set a default
        if transaction_counter is not None and isinstance(transaction_counter, int):
            self.log.info("Found the 'transaction_counter' state: " + str(transaction_counter))
            transactional_state["transaction_counter"] = transaction_counter + 1
            self.log.info("Updating the the 'transaction_counter' state to: " +
                          str(transactional_state["transaction_counter"]))
        else:
            self.log.info("The 'transaction_counter' state does not exist")
            transactional_state["transaction_counter"] = 1
            self.log.info("Writing '" + str(transactional_state["transaction_counter"]) +
                          "' to the 'transaction_counter' state")

        return CheckResponse(transactional_state=transactional_state, persistent_state=persistent_state)
