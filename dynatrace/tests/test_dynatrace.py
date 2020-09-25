# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.dynatrace import DynatraceCheck
from stackstate_checks.base.stubs import topology


def test_check(aggregator, instance):
    check = DynatraceCheck('dynatrace', {}, {})
    check.run()
    topology.get_snapshot(check.check_id)

    aggregator.assert_all_metrics_covered()
