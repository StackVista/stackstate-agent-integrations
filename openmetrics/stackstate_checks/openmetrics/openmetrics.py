# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base.checks.openmetrics import OpenMetricsBaseCheck
from stackstate_checks.base import AgentIntegrationInstance


class OpenMetricsCheck(OpenMetricsBaseCheck):
    def get_instance_key(self, instance):
        return AgentIntegrationInstance(self.name or 'openmetrics', self.cluster_name)
