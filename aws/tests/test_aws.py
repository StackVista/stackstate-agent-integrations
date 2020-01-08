# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.aws import AwsCheck


def test_check(aggregator, instance):
    check = AwsCheck('aws', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
