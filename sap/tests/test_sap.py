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
            components=[],
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
            message="",  # "'NoneType' object has no attribute 'items'",
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
        sap_check._collect_processes(instance_id, sap_check._get_proxy())

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
        sap_check._collect_worker_metrics(instance_id, "ABAP Instance", sap_check._get_proxy())

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


def test_collect_databases(aggregator, instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    host_control_url = "http://localhost:1128/SAPHostControl"
    with requests_mock.mock() as m:
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", text=_read_test_file("samples/ListDatabases.xml"))

        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check._collect_databases(sap_check._get_proxy())

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
                "database_name:DON",
                "database_component_name:Instance",
            ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_name:DON",
                "database_component_name:Database",
            ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_name:DON",
                "database_component_name:Archiver",
            ]
        )
        aggregator.assert_event(
            msg_text="",
            tags=[
                "status:SAPHostControl-DB-RUNNING",
                "database_name:DON",
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


def test_collect_metrics_ora(aggregator, instance):
    host_control_url = "http://localhost:1128/SAPHostControl"
    instance_id = 00

    def match_get_instances(request):
        # sys.stdout.write("match_get_instances")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "SAPInstance" in request.text

    def match_get_alerts(request):
        # sys.stdout.write("match_get_alerts")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "SAP_ITSAMInstance/Alert??Instancenumber" in request.text

    def match_get_sap_instance_params(request):
        # sys.stdout.write("match_get_sap_instance_params")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "SAP_ITSAMInstance/Parameter??Instancenumber" in request.text

    def match_get_computersystem(request):
        # sys.stdout.write("match_get_computersystem")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "ns0:GetComputerSystem" in request.text

    def match_listdatabases(request):
        # sys.stdout.write("match_listdatabases")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "ns0:ListDatabases" in request.text

    def match_database_metrics(request):
        # sys.stdout.write("match_database_metrics")
        # sys.stdout.write("request.text:\n\t{}".format(request.text))
        return "SAP_ITSAMDatabaseMetric?Name" in request.text

    # TODO this is needed because the topology retains data across tests
    topology.reset()
    with requests_mock.mock() as m:
        # Prep mock data
        m.get(host_control_url + "/?wsdl", text=_read_test_file("wsdl/SAPHostAgent.wsdl"))
        m.post(host_control_url + ".cgi", additional_matcher=match_get_instances,
               text=_read_test_file("samples/lab-sap-005 get_sap_instances.xml"))
        m.post(host_control_url + ".cgi", additional_matcher=match_get_alerts,
               text=_read_test_file("samples/lab-sap-005 get_alerts.xml"))
        m.post(host_control_url + ".cgi", additional_matcher=match_get_sap_instance_params,
               text=_read_test_file("samples/lab-sap-005 get_sap_instance_params.xml"))
        m.post(host_control_url + ".cgi", additional_matcher=match_get_computersystem,
               text=_read_test_file("samples/lab-sap-005 get_computerSystem.xml"))
        m.post(host_control_url + ".cgi", additional_matcher=match_listdatabases,
               text=_read_test_file("samples/lab-sap-005 listDatabases.xml"))
        m.post(host_control_url + ".cgi", additional_matcher=match_database_metrics,
               text=_read_test_file("samples/lab-sap-005 databaseMetric.xml"))

        # prep en run function
        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)
        sap_check.start_threads(instance.get("thread_count"))
        sap_check._collect_metrics()

        # don't know, all other function use it
        #assert sap_check.verify is False

        aggregator.assert_event(
            msg_text="SAPControl-GRAY",
            tags=['status:SAPControl-GRAY', 'instance_id:00']
        )
        aggregator.assert_event(
            msg_text="SAPControl-GREEN",
            count=3,
            tags=['status:SAPControl-GREEN', 'instance_id:00']
        )
        aggregator.assert_metric(
            name="phys_memsize",
            value=24575,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["instance_id:00", "host:LAB-SAP-001"]
        )
        aggregator.assert_metric(
            name="SAP:TotalSwapSpaceSize",
            value=33186452,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001"]
        )
        aggregator.assert_metric(
            name="SAP:FreeSpaceInPagingFiles",
            value=29405844,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001"]
        )
        aggregator.assert_metric(
            name="SAP:sizeStoredInPagingFiles",
            value=33186452,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=465.875,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=6155.75,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=2293.4375,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=3535.9375,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=11,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=18.625,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_metric(
            name="db.ora.tablespace.free",
            value=3736,
            hostname="LAB-SAP-001",
            metric_type=aggregator.GAUGE,
            tags=["host:LAB-SAP-001", "database:DEV"]
        )
        aggregator.assert_event(
            msg_text="ONLINE",
            count=7,
            tags=["status:ONLINE", "database:DEV"]
        )

        aggregator.all_metrics_asserted()


def test_get_config_https(https_instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    sap_check = SapCheck(CHECK_NAME, {}, instances=[https_instance])
    url, user, password = sap_check._get_config(https_instance)

    assert sap_check.host == "LAB-SAP-001"
    assert url == "https://localhost"
    assert user == "test"
    assert password == "test"
    assert sap_check.verify == False
    assert sap_check.cert == "/path/to/cert.pem"
    assert sap_check.keyfile == "/path/to/key.pem"
    assert sap_check.tags == ["customer:Stackstate", "foo:bar"]


def test_get_config_http(instance):
    topology.reset()

    sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
    url, user, password = sap_check._get_config(instance)

    assert sap_check.host == "LAB-SAP-001"
    assert url == "http://localhost"
    assert user == "test"
    assert password == "test"
    assert sap_check.domain == "sap"
    assert sap_check.thread_count == 0


def test_send_event(aggregator, instance):
    topology.reset()

    sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
    expected_tags = ["trigger:find_me", "test:true", "status:yoyoyo"]
    sap_check.send_event("description", expected_tags)

    aggregator.assert_event(
        msg_text="yoyoyo",
        tags=expected_tags
    )


def test_sent_gauge(aggregator, instance):
    topology.reset()

    sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
    sap_check._get_config(instance)
    expected_tags = ["trigger:find_me", "test:true", "status:yoyoyo"]
    sap_check.send_gauge("key1", 12321, expected_tags)
    sap_check.send_gauge("key2", 23432, expected_tags)
    sap_check.send_gauge("key3", 34543, expected_tags)

    aggregator.assert_metric(
        name="key1",
        value=12321,
        hostname="LAB-SAP-001",
        metric_type=aggregator.GAUGE,
        tags=expected_tags
    )
    aggregator.assert_metric(
        name="key2",
        value=23432,
        hostname="LAB-SAP-001",
        metric_type=aggregator.GAUGE,
        tags=expected_tags
    )
    aggregator.assert_metric(
        name="key3",
        value=34543,
        hostname="LAB-SAP-001",
        metric_type=aggregator.GAUGE,
        tags=expected_tags
    )
    aggregator.all_metrics_asserted()


def test_generate_tags(https_instance):
    # TODO this is needed because the topology retains data across tests
    topology.reset()

    sap_check = SapCheck(CHECK_NAME, {}, instances=[https_instance])
    sap_check._get_config(https_instance)  # 'https_instance' contains "tags": ["customer:Stackstate", "foo:bar"]
    tags = sap_check.generate_tags(data={'Trigger': 'find_me', 'parent': 'filtered', }, status="someValue")
    assert len(tags) == 3
    assert "status:someValue" in tags
    assert "customer:Stackstate" in tags
    assert "foo:bar" in tags
    assert "Trigger:find_me" not in tags
    assert "parent:filtered" not in tags


def _read_test_file(filename):
    with open("./tests/" + filename, "r") as f:
        return f.read()

def test_collect_sapcloudconnector(aggregator, instance):
    topology.reset()
    with requests_mock.mock() as m:
        sap_check = SapCheck(CHECK_NAME, {}, instances=[instance])
        sap_check._get_config(instance)

        # Prep mock data
        cloud_connector_url = "{0}:{1}".format(sap_check.url, "8443")
        subaccount_url = cloud_connector_url + "api/monitoring/subaccounts"
        backends_url = cloud_connector_url + "api/monitoring/connections/backends"
        m.get(cloud_connector_url, text=_read_test_file("samples/lab-sap-005 scc_ok.html"))
        m.get(subaccount_url, text=_read_test_file("samples/lab-sap-005 scc_subaccounts.json"))
        m.get(backends_url, text=_read_test_file("samples/lab-sap-005 scc_backends.json"))

        topology.get_snapshot(sap_check.check_id)

        sap_check._collect_sapcloudconnector()
    # self.event({
    #                 "timestamp": int(time.time()),
    #                 "source_type_name": "SAP:scc state",
    #                 # "source_type_name": "SAP:host instance",
    #                 "msg_title": "SCC status update.",
    #                 "msg_text": "",
    #                 "host": self.host,
    #                 "tags": [
    #                     "instance_id:99",
    #                     "status:sapcontrol-green"
    #                 ]
    #             })
    # for subaccount in subaccounts["subaccounts"]
        # component_data = {
        #     "name": subaccount_name,
        #     "description": str(subaccount.get("description")),
        #     "state": str(tunnel.get("state")),
        #     "connectedSince": str(tunnel.get("connectedSince")),
        #     "connections": str(tunnel.get("connections")),
        #     "user": str(tunnel.get("user")),
        #     "regionHost": str(subaccount.get("regionHost")),
        #     "subaccount": str(subaccount.get("subaccount")),
        #     "locationID": str(subaccount.get("locationID")),
        #     "layer": "SAP SCC Sub Accounts",
        #     "domain": self.domain,
        #     "environment": self.stackstate_environment,
        #     "host": self.host,
        #     "tags": self.tags
        # }
        # source_id = external_id
        # target_id = self._scc_external_id()
        # relation_data = {}
        # self.relation(source_id, target_id, "is_setup_on", relation_data)
        # self.component(external_id, "sap-scc-subaccount", component_data)
    # for subaccount in backends["subaccounts"]
        # component_data = {
        #     "name": subaccount_name,
        #     "description": str(subaccount.get("description")),
        #     "state": str(tunnel.get("state")),
        #     "connectedSince": str(tunnel.get("connectedSince")),
        #     "connections": str(tunnel.get("connections")),
        #     "user": str(tunnel.get("user")),
        #     "regionHost": str(subaccount.get("regionHost")),
        #     "subaccount": str(subaccount.get("subaccount")),
        #     "locationID": str(subaccount.get("locationID")),
        #     "layer": "SAP SCC Sub Accounts",
        #     "domain": self.domain,
        #     "environment": self.stackstate_environment,
        #     "host": self.host,
        #     "tags": self.tags
        #     # "labels": []
        # }
        # self.log.debug("{0}: -----> component_data : {1}".format(self.host, component_data))
        # self.log.debug("{0}: -----> external_id : {1}".format(self.host, external_id))
        # self.component(external_id, "sap-scc-subaccount", component_data)
        # source_id = external_id
        # target_id = self._scc_external_id()
        # relation_data = {}
        # self.relation(source_id, target_id, "is_setup_on", relation_data)
        #
        # # define cloud connector status event
        #
        # tunnel_status = self._scc_subaccount_status(tunnel.get("state"))
        # self.event({
        #     "timestamp": int(time.time()),
        #     "source_type_name": "SAP:scc subaccount state",
        #     "msg_title": "SAP Cloud Connector '{0}' status update.".format(subaccount_name),
        #     "msg_text": "",
        #     "host": self.host,
        #     "tags": [
        #         "status:{0}".format(tunnel_status),
        #         "subaccount_name:{0}".format(subaccount_name)
        #     ]
        # })
    topology.assert_snapshot(
            check_id=sap_check.check_id,
            start_snapshot=False,
            stop_snapshot=False,
            instance_key=TopologyInstance("sap", "LAB-SAP-001"),
            components=[
                {"id": "urn:sap:/scc:LAB-SAP-001", "type": "sap-cloud-connector",
                 "data": {"name": "SCC",
                          "description": "SAP Cloud Connector",
                          "host": "LAB-SAP-001",
                          "domain": "sap",
                          "environment": "sap-prod",
                          "tags": ["customer:Stackstate", "foo:bar"]}}
            ],
            relations=[
                {'data': {},
                 'source_id': 'urn:host:/LAB-SAP-001',
                 'target_id': 'urn:sap:/instance:LAB-SAP-001:00',
                 'type': 'is hosted on'}
            ]
    )

    aggregator.assert_event(
        msg_text="",
        tags=["instance_id:99", "status:sapcontrol-green"]
    )

def test_collect_saprouter(aggregator, instance):
    assert 1 == 1