# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)


def test_check(aggregator, solarwinds_check):
    solarwinds_check.run()

    aggregator.assert_all_metrics_covered()
