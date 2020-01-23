# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json

import pytest
from munch import munchify
import requests_mock

from stackstate_checks.sap import SapCheck
from stackstate_checks.base import ConfigurationError, TopologyInstance, AgentCheck
from stackstate_checks.base.stubs import topology

CHECK_NAME = 'sap-test'


def test_missing_conf(instance_empty):
    sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance_empty])
    with pytest.raises(ConfigurationError, match=r"Missing.*in instance configuration"):
        sap_check.check(instance_empty)


# def test_worker_free_metrics(aggregator, instance):
#     instance_id = "00"
#     with open("./tests/samples/ABAPGetWPTable.json") as f:
#         worker_processes = munchify(json.load(f))
#     sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance])
#     sap_check._collect_worker_free_metrics(instance_id, worker_processes)
#
#     expected_tags = ["instance_id:{0}".format(instance_id)]
#     aggregator.assert_metric(
#         name="DIA_workers_free",
#         tags=expected_tags,
#         value=9
#     )
#     aggregator.assert_metric(
#         name="BTC_workers_free",
#         tags=expected_tags,
#         value=3
#     )


def test_cannot_connect_to_host_control():
    pass


def test_host_collection(aggregator, instance):
    with open("./tests/wsdl/HostControl.wsdl") as f:
        host_control_wsdl = f.read()
    with open("./tests/samples/GetCIMObject-NoResult.xml") as f:
        instances_response = f.read()

    host_control_url = "{0}:1128/SAPHostControl".format(instance["url"])
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=host_control_wsdl)
        m.post(host_control_url + ".cgi", text=instances_response)

        sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance])
        sap_check.check(instance)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", instance["host"]),
            components=[{"id": "urn:host:/{0}".format(instance["host"]), "type": "sap_host", "data": {}}])

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:sap-host-control-success",
                "host:{0}".format(instance["host"])
            ]
        )

        aggregator.assert_service_check(
            name=SapCheck.SERVICE_CHECK_NAME,
            status=AgentCheck.OK,
            message="OK",
            tags=[]
        )


def test_sap_instances():
    pass


def test_sap_instance_processes():
    pass


def test_sap_instance_free_worker_metrics():
    # only ABAP
    pass


def test_sap_instance_phisycal_memory_metrics():
    pass
