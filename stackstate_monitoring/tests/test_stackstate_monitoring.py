# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.stackstate_monitoring import StackstateMonitoringCheck


def test_check(aggregator, instance):
    check = StackstateMonitoringCheck('stackstate_monitoring', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
