# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.base.checks.openmetrics import OpenMetricsBaseCheck
from stackstate_checks.base import AgentIntegrationInstance

try:
    # this module is only available in agent 6
    from datadog_agent import get_clustername
except ImportError:
    def get_clustername():
        return "test-cluster-name"


class OpenMetricsCheck(OpenMetricsBaseCheck):
    def get_instance_key(self, instance):
        return AgentIntegrationInstance("openmetrics", get_clustername())
