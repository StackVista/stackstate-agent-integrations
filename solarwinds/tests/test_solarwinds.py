# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.solarwinds import SolarwindsCheck


def test_check(aggregator, instance):
    check = SolarwindsCheck('solarwinds', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
