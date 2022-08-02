# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.splunk_event import SplunkEventCheck


def test_check(aggregator, instance):
    check = SplunkEventCheck('splunk_event', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
