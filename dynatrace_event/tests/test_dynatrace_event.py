# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dynatrace_event import DynatraceEventCheck


def test_check(aggregator, instance):
    check = DynatraceEventCheck('dynatrace_event', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
