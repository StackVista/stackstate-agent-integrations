# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# project
from stackstate_checks.base import AgentCheck, AgentIntegrationInstance


class AgentIntegrationSampleCheck(AgentCheck):
    def get_instance_key(self, instance):
        return AgentIntegrationInstance()

    def check(self, instance):
        pass
