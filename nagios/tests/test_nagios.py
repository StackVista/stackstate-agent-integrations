# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.nagios import NagiosCheck


def test_check(aggregator, instance):
    check = NagiosCheck('nagios', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
