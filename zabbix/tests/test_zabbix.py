# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest
import unittest
import mock
import json

from stackstate_checks.zabbix import ZabbixCheck
from stackstate_checks.base import ConfigurationError, AgentCheck
from stackstate_checks.base.stubs import topology, aggregator

CHECK_NAME = 'zabbix'


class TestZabbixInvalidConfig(unittest.TestCase):

    def test_missing_zabbix_url(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'user': 'Admin',
                    'password': 'zabbix'
                }
            ]
        }

        with self.assertRaises(ConfigurationError) as context:
            self.check = ZabbixCheck(CHECK_NAME, config, instances=[config["instances"]])
            self.check.get_instance_key(config["instances"][0])
        self.assertEqual('Missing API url in configuration.', str(context.exception))

    def test_missing_zabbix_user(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'url': "http://host/zabbix/api_jsonrpc.php",
                    'password': 'zabbix'
                }
            ]
        }

        with self.assertRaises(ConfigurationError) as context:
            self.check = ZabbixCheck(CHECK_NAME, config, instances=[config["instances"]])
            self.check.check(config["instances"][0])
        self.assertEqual('Missing API user in configuration.', str(context.exception))

    def test_missing_zabbix_password(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'url': "http://host/zabbix/api_jsonrpc.php",
                    'user': 'Admin'
                }
            ]
        }
        with self.assertRaises(ConfigurationError) as context:
            self.check = ZabbixCheck(CHECK_NAME, config, instances=[config["instances"]])
            self.check.check(config["instances"][0])
        self.assertEqual('Missing API password in configuration.', str(context.exception))


@pytest.mark.usefixtures("instance")
class TestZabbix(unittest.TestCase):

    _config = {
        'init_config': {},
        'instances': [
            {
                'url': "http://host/zabbix/api_jsonrpc.php",
                'user': 'Admin',
                'password': 'zabbix'
            }
        ]
    }

    @staticmethod
    def _apiinfo_response():
        return {
            "jsonrpc": "2.0",
            "result": ["4.0.4"],
            "id": 1
        }

    @staticmethod
    def _zabbix_host_response(maintenance_mode="0"):
        return {
            "jsonrpc": "2.0",
            "result": [
                {
                    "hostid": "10084",
                    "host": "zabbix01.example.com",
                    "name": "Zabbix server",
                    "maintenance_status": maintenance_mode,
                    "groups": [
                        {
                            "groupid": "4",
                            "name": "Zabbix servers"
                        }
                    ]
                }
            ],
            "id": 1
        }

    @staticmethod
    def _zabbix_problem():
        return {
            "jsonrpc": "2.0",
            "result": [
                {
                    "eventid": "14",
                    "source": "0",
                    "object": "0",
                    "objectid": "13491",
                    "clock": "1549878981",
                    "ns": "221836547",
                    "r_eventid": "0",
                    "r_clock": "0",
                    "r_ns": "0",
                    "correlationid": "0",
                    "userid": "0",
                    "name": "Zabbix agent on Zabbix server is unreachable for 5 minutes",
                    "acknowledged": "0",
                    "severity": "3",
                    "acknowledges": [],
                    "suppressed": 0
                }
            ],
            "id": 1
        }

    @staticmethod
    def _zabbix_trigger():
        return {
            "jsonrpc": "2.0",
            "result": [
                {
                    "triggerid": "13491",
                    "expression": "{12900}=1",
                    "description": "Zabbix agent on {HOST.NAME} is unreachable for 5 minutes",
                    "url": "",
                    "status": "0",
                    "value": "1",
                    "priority": "3",
                    "lastchange": "1549878981",
                    "comments": "",
                    "error": "",
                    "templateid": "10047",
                    "type": "0",
                    "state": "0",
                    "flags": "0",
                    "recovery_mode": "0",
                    "recovery_expression": "",
                    "correlation_mode": "0",
                    "correlation_tag": "",
                    "manual_close": "0"
                }
            ],
            "id": 1
        }

    @staticmethod
    def _zabbix_event():
        return {
            "jsonrpc": "2.0",
            "result": [
                {
                    "eventid": "14",
                    "value": "1",
                    "severity": "3",
                    "acknowledged": "0",
                    "hosts": [
                        {
                            "hostid": "10084"
                        }
                    ],
                    "relatedObject": {
                        "triggerid": "13491",
                        "description": "Zabbix agent on {HOST.NAME} is unreachable for 5 minutes",
                        "priority": "3"
                    }
                }
            ],
            "id": 1
        }

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        config = {}
        self.check = ZabbixCheck(CHECK_NAME, config, instances=[self.instance])

    def test_zabbix_topology_hosts(self):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"
        self.check.retrieve_problems = lambda url, auth: []
        self.check.retrieve_events = lambda url, auth, event_ids: []

        self.check.check(self.instance)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)

        component = topo_instances['components'][0]
        expected_identifier = ["zabbix01.example.com"]
        self.assertEqual(component['id'], 'urn:host:/zabbix01.example.com')
        self.assertEqual(component['type'], 'zabbix_host')
        self.assertEqual(component['data']['name'], 'Zabbix server')
        self.assertEqual(component['data']['host_id'], '10084')
        self.assertEqual(component['data']['host'], 'zabbix01.example.com')
        self.assertEqual(component['data']['layer'], 'Host')
        self.assertEqual(component['data']['domain'], 'Zabbix servers')
        self.assertEqual(component['data']['identifiers'], expected_identifier)
        self.assertEqual(component['data']['environment'], 'Production')
        self.assertEqual(component['data']['host_groups'], ['Zabbix servers'])

        labels = component['data']['labels']
        for label in ['zabbix', 'host group:Zabbix servers']:
            if label not in labels:
                self.fail("Component does not have label '%s'." % label)

    def test_zabbix_topology_hosts_no_component(self):
        """
        Test should not return any hosts as host is in maintenance mode
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response(maintenance_mode="1")
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"
        self.check.retrieve_problems = lambda url, auth: []
        self.check.retrieve_events = lambda url, auth, event_ids: []

        self.check.check(self.instance)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 0)
        self.assertEqual(len(topo_instances['relations']), 0)

    def test_zabbix_topology_non_default_environment(self):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            else:
                self.fail("TEST FAILED on making invalid request")

        self.instance['stackstate_environment'] = 'MyTestEnvironment'
        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"
        self.check.retrieve_problems = lambda url, auth: []
        self.check.retrieve_events = lambda url, auth, event_ids: []

        self.check.check(self.instance)

        topo_instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)

        component = topo_instances['components'][0]
        self.assertEqual(component['data']['environment'], 'MyTestEnvironment')

        labels = component['data']['labels']
        for label in ['zabbix', 'host group:Zabbix servers']:
            if label not in labels:
                self.fail("Component does not have label '%s'." % label)

    def test_zabbix_topology_multiple_host_groups(self):
        """
        Zabbix hosts can be placed in multiple host groups.
        When there is only one host group we place the host component in the StackState domain with the
        host group's name.
        However, when there are multiple host groups we use StackState domain 'Zabbix'
        """

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                response = self._zabbix_host_response()
                response['result'][0]['groups'].append(
                    {
                        "groupid": "5",
                        "name": "MyHostGroup"
                    }
                )
                return response
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"
        self.check.retrieve_problems = lambda url, auth: []
        self.check.retrieve_events = lambda url, auth, event_ids: []

        self.check.check(self.instance)

        topo_instances = topology.get_snapshot(self.check.check_id)

        self.assertEqual(len(topo_instances['components']), 1)
        self.assertEqual(len(topo_instances['relations']), 0)
        # Start and Stop Snapshot should be True
        self.assertEqual(topo_instances.get("start_snapshot"), True)
        self.assertEqual(topo_instances.get("stop_snapshot"), True)

        component = topo_instances['components'][0]
        self.assertEqual(component['data']['domain'], 'Zabbix')
        labels = component['data']['labels']
        for label in ['zabbix', 'host group:Zabbix servers', 'host group:MyHostGroup']:
            if label not in labels:
                self.fail("Component does not have label '%s'." % label)

        # check if OK service check generated
        service_checks = aggregator.service_checks('Zabbix')
        self.assertEqual(AgentCheck.OK, service_checks[0].status)

    def test_zabbix_problems(self):

        # TODO this is needed because the aggregator retains events data across tests
        aggregator.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            elif name == "problem.get":
                return self._zabbix_problem()
            elif name == "trigger.get":
                return self._zabbix_trigger()
            elif name == "event.get":
                return self._zabbix_event()
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"

        self.check.check(self.instance)

        events = aggregator.events

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_type_name'], 'Zabbix')
        tags = events[0]['tags']

        for tag in ['host_id:10084', 'severity:3',
                    "triggers:['Zabbix agent on {HOST.NAME} is unreachable for 5 minutes']",
                    "host:zabbix01.example.com", "host_name:Zabbix server"]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

    def test_zabbix_no_problems(self):
        """
        When there are no problems, we are expecting all host components to go to green.
        To make this happen we need to send an event that says all is OK.
        """
        # TODO this is needed because the aggregator retains events data across tests
        aggregator.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            elif name == "problem.get":
                response = self._zabbix_problem()
                response['result'] = []
                return response
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"

        self.check.check(self.instance)
        events = aggregator.events
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_type_name'], 'Zabbix')
        tags = events[0]['tags']

        for tag in ['host_id:10084', 'severity:0', "triggers:[]",
                    "host:zabbix01.example.com", "host_name:Zabbix server"]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

    def test_zabbix_determine_most_severe_state(self):
        """
            A host can have multiple active problems.
            From the active problems we determine the most severe state and send that to StackState
        """
        # TODO this is needed because the aggregator retains events data across tests
        aggregator.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            elif name == "problem.get":
                response = self._zabbix_problem()
                response['result'].append({
                    "eventid": "100",
                    "source": "0",
                    "object": "0",
                    "objectid": "111",
                    "clock": "1549878981",
                    "ns": "221836547",
                    "r_eventid": "0",
                    "r_clock": "0",
                    "r_ns": "0",
                    "correlationid": "0",
                    "userid": "0",
                    "name": "My very own problem",
                    "acknowledged": "0",
                    "severity": "5",
                    "acknowledges": [],
                    "suppressed": 0
                })
                return response
            elif name == "trigger.get":
                return self._zabbix_trigger()
            elif name == "event.get":
                response = self._zabbix_event()
                response['result'].append({
                    "eventid": "100",
                    "value": "1",
                    "severity": "5",
                    "acknowledged": "0",
                    "hosts": [
                        {
                            "hostid": "10084"
                        }
                    ],
                    "relatedObject": {
                        "triggerid": "111",
                        "description": "My very own problem",
                        "priority": "5"
                    }
                })
                return response
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"

        self.check.check(self.instance)
        events = aggregator.events

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_type_name'], 'Zabbix')
        tags = events[0]['tags']

        for tag in [
            'host_id:10084',
            'severity:5',
            "triggers:['Zabbix agent on {HOST.NAME} is unreachable for 5 minutes', 'My very own problem']",
            "host:zabbix01.example.com",
            "host_name:Zabbix server"
        ]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

    def validate_requests_ssl_verify_setting(self, instance_to_use, expected_verify_value):
        """
        Helper for testing whether the yaml setting ssl_verify is respected by mocking requests.get
        Mocking all the Zabbix functions that talk HTTP via requests.get, excluding the function `check_connection`
        Function check_connection is the first function that talks HTTP.
        """
        with mock.patch('requests.get') as mock_get:
            with mock.patch('yaml.safe_load'):
                self.check.login = lambda url, user, password: "dummyauthtoken"
                self.check.retrieve_hosts = lambda x, y: []
                self.check.retrieve_problems = lambda url, auth: []
                self.check.retrieve_events = lambda url, auth, event_ids: []
                self.check.check(instance_to_use)
                mock_get.assert_called_once_with('http://10.0.0.1/zabbix/api_jsonrpc.php',
                                                 json={'params': {}, 'jsonrpc': '2.0', 'method': 'apiinfo.version',
                                                       'id': 1},
                                                 verify=expected_verify_value)

    def test_zabbix_respect_false_ssl_verify(self):
        config = self.instance
        config['ssl_verify'] = False
        self.validate_requests_ssl_verify_setting(config, False)

    def test_zabbix_respect_true_ssl_verify(self):
        config = self.instance
        config['ssl_verify'] = True
        self.validate_requests_ssl_verify_setting(config, True)

    def test_zabbix_respect_default_ssl_verify(self):
        self.validate_requests_ssl_verify_setting(self.instance, True)

    def test_zabbix_disabled_triggers(self):
        """
        When there are no triggers enabled and return empty list for `trigger.get` call, then we are expecting no
        problems and host will become green if it was red because there will be an event without any severity/problems.
        """
        # TODO this is needed because the aggregator retains events data across tests
        aggregator.reset()

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            elif name == "problem.get":
                response = self._zabbix_problem()
                return response
            elif name == "trigger.get":
                response = self._zabbix_trigger()
                response['result'] = []
                return response
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"

        self.check.check(self.instance)
        events = aggregator.events
        self.assertEqual(len(events), 1)
        tags = events[0]['tags']
        for tag in [
            'host_id:10084',
            "host:zabbix01.example.com",
            "host_name:Zabbix server",
            "severity:0",
            "triggers:[]"
        ]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

        # check if OK service check generated
        service_checks = aggregator.service_checks('Zabbix')
        self.assertEqual(AgentCheck.OK, service_checks[0].status)

    def test_zabbix_acknowledge_problem(self):
        """
        When there are problems, we are expecting all host components to go to yellow/red.
        But acknowledging the problem should make the host components go back to green
        To make this happen we need to send an event that says the problem is `acknowledged`.
        """
        # TODO this is needed because the aggregator retains events data across tests
        aggregator.reset()

        self.event_response = {}
        self.second_run = False

        def _mocked_method_request(url, name, auth=None, params={}, request_id=1):
            if name == "apiinfo.version":
                return self._apiinfo_response()
            elif name == "host.get":
                return self._zabbix_host_response()
            elif name == "problem.get":
                response = self._zabbix_problem()
                return response
            elif name == "trigger.get":
                response = self._zabbix_trigger()
                return response
            elif name == "event.get":
                self.event_response = self._zabbix_event()
                if not self.second_run:
                    # acknowledge the problem
                    self.event_response['result'][0]['acknowledged'] = '1'
                    self.second_run = True
                else:
                    self.event_response['result'][0]['acknowledged'] = '0'
                return self.event_response
            else:
                self.fail("TEST FAILED on making invalid request")

        self.check.method_request = _mocked_method_request
        self.check.login = lambda url, user, password: "dummyauthtoken"

        self.check.check(self.instance)
        events = aggregator.events
        self.assertEqual(len(events), 1)
        tags = events[0]['tags']
        for tag in [
            'host_id:10084',
            "host:zabbix01.example.com",
            "host_name:Zabbix server",
            "severity:0",
            "triggers:[]"
        ]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

        aggregator.reset()
        # second run to revert the acknowledged problem to create the event again
        self.check.check(self.instance)
        events = aggregator.events
        self.assertEqual(len(events), 1)
        tags = events[0]['tags']
        for tag in [
            'host_id:10084',
            "host:zabbix01.example.com",
            "host_name:Zabbix server",
            "severity:3",
            "triggers:['Zabbix agent on {HOST.NAME} is unreachable for 5 minutes']"
        ]:
            if tag not in tags:
                self.fail("Event does not have tag '%s', got: %s." % (tag, tags))
        self.assertEqual(len(tags), 5)

    @mock.patch('requests.get')
    def test_method_request(self, mocked_get):
        event_resp = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "triggerid": "13491",
                    "expression": u"{12900}=1",
                    "description": u"Zabbix agent on {HOST.NAME} is unreachable for 5 minutes",
                    "url": "",
                    "status": "0",
                    "value": "1",
                    "priority": "3",
                    "lastchange": "1549878981",
                    "comments": "",
                    "error": "",
                    "templateid": "10047",
                    "type": "0",
                    "state": "0",
                    "flags": "0",
                    "recovery_mode": "0",
                    "recovery_expression": "",
                    "correlation_mode": "0",
                    "correlation_tag": "",
                    "manual_close": "0"
                }
            ],
            "id": 1
        }
        mocked_get.return_value = mock.MagicMock(status_code=200, text=json.dumps(event_resp))
        self.check.ssl_verify = False
        resp = self.check.method_request("http://host/zabbix/api_jsonrpc.php", "events.get")
        self.assertEqual(u"{12900}=1", resp.get("result")[0].get("expression"))
