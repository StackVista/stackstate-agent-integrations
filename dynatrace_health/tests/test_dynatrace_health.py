# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dynatrace_health import DynatraceHealthCheck


def test_check(aggregator, instance):
    check = DynatraceHealthCheck('dynatrace_health', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
