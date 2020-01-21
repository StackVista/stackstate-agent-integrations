# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

import pytest
from munch import munchify

from stackstate_checks.sap import SapCheck

from stackstate_checks.base import ConfigurationError
from stackstate_checks.base.stubs import topology

CHECK_NAME = 'sap-test'


# def test_check(aggregator, instance):
#     check = SapCheck("test-sap1", {}, {}, instances=[instance])
#     check.check(instance)
#
#     print(json.dumps(topology.get_snapshot(''), indent=4, sort_keys=True))


def test_missing_conf(instance_empty):
    sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance_empty])
    with pytest.raises(ConfigurationError, match=r"Missing.*in instance configuration"):
        sap_check.check(instance_empty)


def test_worker_free_metrics(aggregator, instance):
    instance_id = "00"
    with open("./tests/samples/ABAPGetWPTable.json") as f:
        worker_processes = munchify(json.load(f))
    sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance])
    sap_check._collect_worker_free_metrics(instance_id, worker_processes)

    expected_tags = ["instance_id:{0}".format(instance_id)]
    aggregator.assert_metric(
        name="DIA_workers_free",
        tags=expected_tags,
        value=9
    )
    aggregator.assert_metric(
        name="BTC_workers_free",
        tags=expected_tags,
        value=3
    )


def test_cannot_connect_to_host_control():
    pass