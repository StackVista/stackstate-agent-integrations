# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import requests_mock

from stackstate_checks.sap import SapCheck
from stackstate_checks.base import ConfigurationError, TopologyInstance, AgentCheck
from stackstate_checks.base.stubs import topology

CHECK_NAME = "sap-test"


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


def test_check_run_no_sap_instances(aggregator, instance):
    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/HostControl.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetCIMObject-NoResult.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance])
        sap_check.check(instance)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[{"id": "urn:host:/LAB-SAP-001", "type": "sap_host", "data": {"host": "LAB-SAP-001"}}])

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


def test_collect_only_hosts(aggregator, instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/HostControl.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetCIMObject.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_hosts()

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:host:/LAB-SAP-001", "type": "sap_host", "data": {"host": "LAB-SAP-001"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:67",
                 "type": "sap_instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "CDA",
                          "sid": "CDA",
                          "system_number": "67",
                          "type": "Solution Manager Diagnostic Agent",
                          "version": "753, patch 200, changelist 1844229"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:00",
                 "type": "sap_instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "00",
                          "type": "ABAP Instance",
                          "version": "753, patch 401, changelist 1927964"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:01",
                 "type": "sap_instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "01",
                          "type": "Central Services Instance",
                          "version": "753, patch 401, changelist 1927964"}}
            ],
            relations=[
                {'data': {},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:67',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:01',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'}
            ]
        )

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:sap-host-control-success",
                "host:{0}".format(instance["host"])
            ]
        )


def test_sap_instance_processes():
    pass


def test_sap_instance_free_worker_metrics():
    # only ABAP
    pass


def test_sap_instance_phisycal_memory_metrics():
    pass


def _read_test_file(filename):
    f = open("./tests/" + filename)
    c = f.read()
    f.close()
    return c
