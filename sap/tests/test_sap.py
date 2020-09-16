# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import requests
import requests_mock

from stackstate_checks.sap import SapCheck
from stackstate_checks.base import ConfigurationError, TopologyInstance, AgentCheck, AgentIntegrationTestUtil
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
        sap_check.run()
        topology.get_snapshot(sap_check.check_id)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host",
                 "data": {"host": "LAB-SAP-001", 'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          "domain": "sap", "environment": "sap-prod"}}
            ],
            relations=[],
        )

        AgentIntegrationTestUtil.assert_integration_snapshot(sap_check, 'sap:LAB-SAP-001')

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
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetCIMObject-NoResult.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check.run()
        topology.get_snapshot(sap_check.check_id)

        topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=True,
            stop_snapshot=True,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host",
                 "data": {"host": "LAB-SAP-001", 'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          "domain": "sap", "environment": "sap-prod"}}
            ],
            relations=[],
        )

        AgentIntegrationTestUtil.assert_integration_snapshot(sap_check, 'sap:LAB-SAP-001')

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
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
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
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host", "data": {"host": "LAB-SAP-001",
                                                                             'tags': ['integration-type:sap',
                                                                                      'integration-url:LAB-SAP-001'],
                                                                             "domain": "sap",
                                                                             "environment": "sap-prod"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:67",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          "name": "CDA",
                          "sid": "CDA",
                          "system_number": "67",
                          "type": "Solution Manager Diagnostic Agent",
                          "version": "753, patch 200, changelist 1844229",
                          "domain": "sap", "environment": "sap-prod"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:00",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "00",
                          "type": "ABAP Instance",
                          "version": "753, patch 401, changelist 1927964",
                          "domain": "sap", "environment": "sap-prod"}},
                {"id": "urn:sap:/instance:LAB-SAP-001:01",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "01",
                          "type": "Central Services Instance",
                          "version": "753, patch 401, changelist 1927964",
                          "domain": "sap", "environment": "sap-prod"}}
            ],
            relations=[
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:67',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
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
    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/GetProcessList.xml"))

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
                          'elapsedtime': '0:56:22',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          'name': 'disp+work.EXE',
                          'pid': 5972,
                          'starttime': '2020 07 31 08:37:19',
                          "domain": "sap", "environment": "sap-prod"},
                 'id': 'urn:process:/LAB-SAP-001:00:5972',
                 'type': 'sap-process'},
                {'data': {'description': 'IGS Watchdog',
                          'elapsedtime': '0:56:22',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          'name': 'igswd.EXE',
                          'pid': 15564,
                          'starttime': '2020 07 31 08:37:19',
                          "domain": "sap", "environment": "sap-prod"},
                 'id': 'urn:process:/LAB-SAP-001:00:15564',
                 'type': 'sap-process'},
                {'data': {'description': 'Gateway',
                          'elapsedtime': '0:56:21',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          'name': 'gwrd',
                          'pid': 16624,
                          'starttime': '2020 07 31 08:37:20',
                          "domain": "sap", "environment": "sap-prod"},
                 'id': 'urn:process:/LAB-SAP-001:00:16624',
                 'type': 'sap-process'},
                {'data': {'description': 'ICM',
                          'elapsedtime': '0:56:21',
                          'host': 'LAB-SAP-001',
                          'labels': [],
                          'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                          'name': 'icman',
                          'pid': 11508,
                          'starttime': '2020 07 31 08:37:20',
                          "domain": "sap", "environment": "sap-prod"},
                 'id': 'urn:process:/LAB-SAP-001:00:11508',
                 'type': 'sap-process'}
            ],
            relations=[
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:process:/LAB-SAP-001:00:5972',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:process:/LAB-SAP-001:00:15564',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:process:/LAB-SAP-001:00:16624',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'},
                {'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                 'source_id': 'urn:process:/LAB-SAP-001:00:11508',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'runs on'}
            ]
        )

        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:5972",
                "instance_id:" + instance_id,
                "starttime:2020 07 31 08:37:19",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:15564",
                "instance_id:" + instance_id,
                "starttime:2020 07 31 08:37:19",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:16624",
                "instance_id:" + instance_id,
                "starttime:2020 07 31 08:37:20",
            ]
        )
        aggregator.assert_event(
            msg_text="Running",
            tags=[
                "status:SAPControl-GREEN",
                "pid:11508",
                "instance_id:" + instance_id,
                "starttime:2020 07 31 08:37:20",
            ]
        )

        aggregator.all_metrics_asserted()


def test_collect_worker_metrics(aggregator, instance):
    # Only ABAP instances

    instance_id = "00"
    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/ABAPGetWPTable.xml"))

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
    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/ParameterValue.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_memory_metric(instance_id, sap_check._get_proxy(instance_id))

        expected_tags = ["instance_id:" + instance_id]
        aggregator.assert_metric(
            name="phys_memsize",
            value=32767,
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
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/ListDatabases.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_databases()

        assert sap_check.verify is True

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
                                  'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                                  'labels': [],
                                  "domain": "sap",
                                  "environment": "sap-prod"}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Instance',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Instance',
                                  'database_name': 'DON',
                                  'name': 'Instance',
                                  'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                                  'labels': [],
                                  "domain": "sap",
                                  "environment": "sap-prod"}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Database',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Database',
                                  'database_name': 'DON',
                                  'name': 'Database',
                                  'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                                  'labels': [],
                                  "domain": "sap",
                                  "environment": "sap-prod"}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Archiver',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Archiver',
                                  'database_name': 'DON',
                                  'name': 'Archiver',
                                  'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                                  'labels': [],
                                  "domain": "sap",
                                  "environment": "sap-prod"}},
                        {'type': 'sap-database-component',
                         'id': 'urn:sap:/db_component:LAB-SAP-001:DON:Listener',
                         'data': {'host': 'LAB-SAP-001',
                                  'description': 'Listener',
                                  'database_name': 'DON',
                                  'name': 'Listener',
                                  'tags': ['integration-type:sap', 'integration-url:LAB-SAP-001'],
                                  'labels': [],
                                  "domain": "sap",
                                  "environment": "sap-prod"}}
                        ],
            relations=[{'type': 'is hosted on',
                        'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                        'source_id': 'urn:db:/LAB-SAP-001:DON',
                        'target_id': 'urn:host:/LAB-SAP-001'},
                       {'type': 'runs on',
                        'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Instance',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Database',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
                        'source_id': 'urn:sap:/db_component:LAB-SAP-001:DON:Archiver',
                        'target_id': 'urn:db:/LAB-SAP-001:DON'},
                       {'type': 'runs on',
                        'data': {"domain": "sap", "environment": "sap-prod", "tags": []},
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


def test_collect_only_hosts_create_service_https(aggregator, https_instance):
    """
        Should return the proper host location as defined in the config and doesn't care about WSDL host location
    """
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "https://localhost:1129/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
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
                {"id": "urn:host:/LAB-SAP-001", "type": "sap-host",
                 "data": {"host": "LAB-SAP-001",
                          'tags': ['customer:Stackstate', 'foo:bar', 'integration-type:sap',
                                   'integration-url:LAB-SAP-001'],
                          "domain": None, "environment": None}},
                {"id": "urn:sap:/instance:LAB-SAP-001:67",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['customer:Stackstate', 'foo:bar', 'integration-type:sap',
                                   'integration-url:LAB-SAP-001'],
                          "name": "CDA",
                          "sid": "CDA",
                          "system_number": "67",
                          "type": "Solution Manager Diagnostic Agent",
                          "version": "753, patch 200, changelist 1844229",
                          "domain": None,
                          "environment": None}},
                {"id": "urn:sap:/instance:LAB-SAP-001:00",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['customer:Stackstate', 'foo:bar', 'integration-type:sap',
                                   'integration-url:LAB-SAP-001'],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "00",
                          "type": "ABAP Instance",
                          "version": "753, patch 401, changelist 1927964",
                          "domain": None,
                          "environment": None}},
                {"id": "urn:sap:/instance:LAB-SAP-001:01",
                 "type": "sap-instance",
                 "data": {"host": "LAB-SAP-001",
                          "labels": [],
                          'tags': ['customer:Stackstate', 'foo:bar', 'integration-type:sap',
                                   'integration-url:LAB-SAP-001'],
                          "name": "DON",
                          "sid": "DON",
                          "system_number": "01",
                          "type": "Central Services Instance",
                          "version": "753, patch 401, changelist 1927964",
                          "domain": None,
                          "environment": None}}
            ],
            relations=[
                {'data': {"domain": None, "environment": None, "tags": ['customer:Stackstate', 'foo:bar']},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:67',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {"domain": None, "environment": None, "tags": ['customer:Stackstate', 'foo:bar']},
                 'source_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'target_id': 'urn:host:/LAB-SAP-001',
                 'type': 'is hosted on'},
                {'data': {"domain": None, "environment": None, "tags": ['customer:Stackstate', 'foo:bar']},
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
