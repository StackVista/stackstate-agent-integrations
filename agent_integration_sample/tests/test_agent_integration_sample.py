# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.agent_integration_sample import AgentIntegrationSampleCheck


def test_check(aggregator, instance):
    check = AgentIntegrationSampleCheck('agent_integration_sample', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
