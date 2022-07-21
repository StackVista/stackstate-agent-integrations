# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.agent_v2_integration_sample.agent_v2_integration_sample import agent_v2_integration_base
from stackstate_checks.base.checks.v2.transactional_agent_check import TransactionalAgentCheck
from stackstate_checks.base import AgentIntegrationInstance, HealthStream, HealthStreamUrn
from stackstate_checks.checks import CheckResponse
from random import seed

seed(1)


class AgentV2IntegrationTransactionalSampleCheck(TransactionalAgentCheck):
    def get_health_stream(self, instance):
        return HealthStream(HealthStreamUrn("agent-v2-integration-transactional-sample", "sample"))

    def get_instance_key(self, instance):
        return AgentIntegrationInstance("agent-v2-integration-transactional", "sample")

    def transactional_check(self, instance, transactional_state, persistent_state):
        agent_v2_integration_base(self, instance, "agent-v2-integration-transactional-sample")
        return CheckResponse(transactional_state=transactional_state, persistent_state=persistent_state)
