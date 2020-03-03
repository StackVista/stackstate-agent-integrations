# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.scom import SCOM


def test_check(aggregator, instance):
    check = SCOM('scom', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
