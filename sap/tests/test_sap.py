# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import requests
import requests_mock

from stackstate_checks.sap import SapCheck
from stackstate_checks.base import ConfigurationError, TopologyInstance, AgentCheck
from stackstate_checks.base.stubs import topology

CHECK_NAME = "sap-test"


def test_missing_conf(instance_empty):
    sap_check = SapCheck(CHECK_NAME, {}, instances=[instance_empty])
    with pytest.raises(ConfigurationError, match=r"Missing.*in instance configuration"):
        sap_check.check(instance_empty)


def test_cannot_connect_to_host_control(aggregator, instance):
    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", exc=requests.exceptions.ConnectTimeout)

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check.check(instance)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[{"id": "urn:host:/LAB-SAP-001", "type": "sap-host", "data": {"host": "LAB-SAP-001"}}])

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:sap-host-control-error",
                "host:LAB-SAP-001"
            ]
        )

        aggregator.all_metrics_asserted()

        aggregator.assert_service_check(
            name=SapCheck.SERVICE_CHECK_NAME,
            status=AgentCheck.CRITICAL,
            message="'NoneType' object has no attribute 'items'",
            tags=[]
        )


def test_check_run_no_sap_instances(aggregator, instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/HostControl.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetCIMObject-NoResult.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check.check(instance)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[{"id": "urn:host:/LAB-SAP-001", "type": "sap-host", "data": {"host": "LAB-SAP-001"}}])

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:sap-host-control-success",
                "host:LAB-SAP-001"
            ]
        )

        aggregator.all_metrics_asserted()

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

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_hosts()

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host", "data": {"host": "LAB-SAP-001"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:67",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "CDA",
                          "sid": "CDA",
                          "system_number": "67",
                          "type": "Solution Manager Diagnostic Agent",
                          "version": "753, patch 200, changelist 1844229"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:00",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "00",
                          "type": "ABAP Instance",
                          "version": "753, patch 401, changelist 1927964"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:01",
                 "type": "sap-instance",
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
                "host:LAB-SAP-001"
            ]
        )

        aggregator.all_metrics_asserted()


def test_collect_processes(aggregator, instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    instance_id = "00"
    host_agent_url = "http://localhost:50013/"
    with requests_mock.mock() as m:
        m.get(host_agent_url + "SAPHostAgent/?wsdl", text=_read_test_file("wsdl/HostAgent.wsdl"))
        m.post(host_agent_url, text=_read_test_file("samples/GetProcessList.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_processes(instance_id, sap_check._get_proxy(instance_id))

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {'data': {'description': 'Dispatcher',
                          'elapsedtime': '119:16:01',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'name': 'disp+work.EXE',
                          'pid': 4392,
                          'starttime': '2020 01 22 12:52:29'},
                 'id': 'urn:process:/LAB-SAP-001:00:4392',
                 'type': 'sap-process'},
                {'data': {'description': 'IGS Watchdog',
                          'elapsedtime': '119:16:01',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'name': 'igswd.EXE',
                          'pid': 11088,
                          'starttime': '2020 01 22 12:52:29'},
                 'id': 'urn:process:/LAB-SAP-001:00:11088',
                 'type': 'sap-process'},
                {'data': {'description': 'Gateway',
                          'elapsedtime': '119:16:01',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'name': 'gwrd',
                          'pid': 9512,
                          'starttime': '2020 01 22 12:52:29'},
                 'id': 'urn:process:/LAB-SAP-001:00:9512',
                 'type': 'sap-process'},
                {'data': {'description': 'ICM',
                          'elapsedtime': '119:16:01',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'name': 'icman',
                          'pid': 6584,
                          'starttime': '2020 01 22 12:52:29'},
                 'id': 'urn:process:/LAB-SAP-001:00:6584',
                 'type': 'sap-process'}
            ],
            relations=[
                {'data': {},
                 'source_id': 'urn:process:/LAB-SAP-001:00:4392',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {},
                 'source_id': 'urn:process:/LAB-SAP-001:00:11088',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {},
                 'source_id': 'urn:process:/LAB-SAP-001:00:9512',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {},
                 'source_id': 'urn:process:/LAB-SAP-001:00:6584',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'}
            ]
        )

        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:4392",
                "instance_id:" + instance_id,
                "starttime:2020 01 22 12:52:29",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:11088",
                "instance_id:" + instance_id,
                "starttime:2020 01 22 12:52:29",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:9512",
                "instance_id:" + instance_id,
                "starttime:2020 01 22 12:52:29",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GRAY",
                "pid:6584",
                "instance_id:" + instance_id,
                "starttime:2020 01 22 12:52:29",
            ]
        )

        aggregator.all_metrics_asserted()


def test_collect_worker_metrics(aggregator, instance):
    # Only ABAP instances

    instance_id = "00"
    host_agent_url = "http://localhost:50013/"
    with requests_mock.mock() as m:
        m.get(host_agent_url + "SAPHostAgent/?wsdl", text=_read_test_file("wsdl/HostAgent.wsdl"))
        m.post(host_agent_url, text=_read_test_file("samples/ABAPGetWPTable.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_worker_metrics(instance_id, "ABAP Instance", sap_check._get_proxy(instance_id))

        expected_tags = ["instance_id:" + instance_id]
        aggregator.assert_metric(
            name="DIA_workers_free",
            value=10,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=expected_tags
        )
        aggregator.assert_metric(
            name="BTC_workers_free",
            value=3,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=expected_tags
        )

        aggregator.all_metrics_asserted()


def test_collect_memory_metric(aggregator, instance):
    instance_id = "00"
    host_agent_url = "http://localhost:50013/"
    with requests_mock.mock() as m:
        m.get(host_agent_url + "SAPHostAgent/?wsdl", text=_read_test_file("wsdl/HostAgent.wsdl"))
        m.post(host_agent_url, text=_read_test_file("samples/ParameterValue.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_memory_metric(instance_id, sap_check._get_proxy(instance_id))

        expected_tags = ["instance_id:" + instance_id]
        aggregator.assert_metric(
            name="phys_memsize",
            value=65535.0,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=expected_tags
        )

        aggregator.all_metrics_asserted()


def test_collect_databases(aggregator, instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/HostControl.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/ListDatabases.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_databases()

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[{'type': 'sap-database',
                         'id': 'urn:db:/LAB-SAP-001:DON',
                         'data': {'vendor': 'ora',
                                  'name': 'DON',
                                  'type': 'ora',
                                  'host': 'lab-sap-001',
                                  'version': '18.0.0.0.0',
                                  'labels': []}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Instance',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Instance',
                                  'database_name': 'DON',
                                  'name': 'Instance',
                                  'labels': []}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Database',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Database',
                                  'database_name': 'DON',
                                  'name': 'Database',
                                  'labels': []}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Archiver',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Archiver',
                                  'database_name': 'DON',
                                  'name': 'Archiver',
                                  'labels': []}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Listener',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Listener',
                                  'database_name': 'DON',
                                  'name': 'Listener',
                                  'labels': []}}
                        ],
            relations=[{'type': 'is hosted on',
                        'data': {},
                        'source_id': 'urn:db:/LAB-SAP-001:DON',
                        'target_id': 'urn:host:/LAB-SAP-001'},
                       {'type': 'runs on',
                        'data': {},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Instance',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Database',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Archiver',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Listener',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'}
                       ]
        )

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_name:DON",
                ]
        )

        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_component_name:Instance",
                ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_component_name:Database",
                ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_component_name:Archiver",
                ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_component_name:Listener",
                ]
        )

        aggregator.all_metrics_asserted()


def test_collect_only_hosts_https(aggregator, https_instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "https://localhost:1129/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/HttpsHostControl.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetCIMObject.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[https_instance])
        sap_check._get_config(https_instance)
        sap_check._collect_hosts()

        assert sap_check.verify is False

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host", "data": {"host": "LAB-SAP-001"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:67",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "CDA",
                          "sid": "CDA",
                          "system_number": "67",
                          "type": "Solution Manager Diagnostic Agent",
                          "version": "753, patch 200, changelist 1844229"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:00",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "00",
                          "type": "ABAP Instance",
                          "version": "753, patch 401, changelist 1927964"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:01",
                 "type": "sap-instance",
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
                "host:LAB-SAP-001"
            ]
        )

        aggregator.all_metrics_asserted()


def _read_test_file(filename):
    f = open("./tests/" + filename)
    c = f.read()
    f.close()
    return c
