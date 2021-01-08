# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.appdynamics import AppDynamicsCheck


def test_check(aggregator, instance):
    check = AppDynamicsCheck('appdynamics', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
