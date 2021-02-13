# -*- coding: utf-8 -*-

# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import mock
import shutil
from schematics import Model
from schematics.types import IntType, StringType, ModelType
import pytest
from six import PY3

from stackstate_checks.checks import AgentCheck, TopologyInstance, AgentIntegrationInstance
from stackstate_checks.base.utils.agent_integration_test_util import AgentIntegrationTestUtil
from stackstate_checks.base.stubs.topology import component, relation


def test_instance():
    """
    Simply assert the class can be instantiated
    """
    AgentCheck()
    # rely on default
    check = AgentCheck()
    assert check.init_config == {}
    assert check.instances == []

    # pass dict for 'init_config', a list for 'instances'
    init_config = {'foo': 'bar'}
    instances = [{'bar': 'baz'}]
    check = AgentCheck(init_config=init_config, instances=instances)
    assert check.init_config == {'foo': 'bar'}
    assert check.instances == [{'bar': 'baz'}]


def test_load_config():
    assert AgentCheck.load_config("raw_foo: bar") == {'raw_foo': 'bar'}


def test_log_critical_error():
    check = AgentCheck()

    with pytest.raises(NotImplementedError):
        check.log.critical('test')


class TestMetricNormalization:
    def test_default(self):
        check = AgentCheck()
        metric_name = u'Klüft inför på fédéral'
        normalized_metric_name = b'Kluft_infor_pa_federal'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_fix_case(self):
        check = AgentCheck()
        metric_name = u'Klüft inför på fédéral'
        normalized_metric_name = b'kluft_infor_pa_federal'

        assert check.normalize(metric_name, fix_case=True) == normalized_metric_name

    def test_prefix(self):
        check = AgentCheck()
        metric_name = u'metric'
        prefix = u'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_prefix_bytes(self):
        check = AgentCheck()
        metric_name = u'metric'
        prefix = b'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_prefix_unicode_metric_bytes(self):
        check = AgentCheck()
        metric_name = b'metric'
        prefix = u'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_underscores_redundant(self):
        check = AgentCheck()
        metric_name = u'a_few__redundant___underscores'
        normalized_metric_name = b'a_few_redundant_underscores'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_underscores_at_ends(self):
        check = AgentCheck()
        metric_name = u'_some_underscores_'
        normalized_metric_name = b'some_underscores'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_underscores_and_dots(self):
        check = AgentCheck()
        metric_name = u'some_.dots._and_._underscores'
        normalized_metric_name = b'some.dots.and.underscores'

        assert check.normalize(metric_name) == normalized_metric_name


class TestMetrics:
    def test_non_float_metric(self, aggregator):
        check = AgentCheck()
        metric_name = 'test_metric'
        with pytest.raises(ValueError):
            check.gauge(metric_name, '85k')
        aggregator.assert_metric(metric_name, count=0)


class TestEvents:
    def test_valid_event(self, aggregator):
        check = AgentCheck()
        event = {
            "timestamp": 123456789,
            "event_type": "new.event",
            "source_type_name": "new.source.type",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": None
        }
        check.event(event)
        aggregator.assert_event('test event test event')

    def test_topology_event(self, telemetry):
        check = AgentCheck()
        event = {
            "timestamp": 123456789,
            "event_type": "new.event",
            "source_type_name": "new.source.type",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": None,
            "context": {
                "element_identifiers": ["urn:test:/value"],
                "source": "test source",
                "category": "test category",
            }
        }
        check.event(event)
        telemetry.assert_topology_event(event)


class TestServiceChecks:
    def test_valid_sc(self, aggregator):
        check = AgentCheck()

        check.service_check("testservicecheck", AgentCheck.OK, tags=None, message="")
        aggregator.assert_service_check("testservicecheck", status=AgentCheck.OK)

        check.service_check("testservicecheckwithhostname", AgentCheck.OK, tags=["foo", "bar"], hostname="testhostname",
                            message="a message")
        aggregator.assert_service_check("testservicecheckwithhostname", status=AgentCheck.OK, tags=["foo", "bar"],
                                        hostname="testhostname", message="a message")

        check.service_check("testservicecheckwithnonemessage", AgentCheck.OK, message=None)
        aggregator.assert_service_check("testservicecheckwithnonemessage", status=AgentCheck.OK, )


class TestTags:
    def test_default_string(self):
        check = AgentCheck()
        tag = 'default:string'
        tags = [tag]

        normalized_tags = check._normalize_tags_type(tags, None)
        normalized_tag = normalized_tags[0]

        assert normalized_tags is not tags
        # Ensure no new allocation occurs
        assert normalized_tag is tag

    def test_bytes_string(self):
        check = AgentCheck()
        tag = b'bytes:string'
        tags = [tag]

        normalized_tags = check._normalize_tags_type(tags, None)
        normalized_tag = normalized_tags[0]

        assert normalized_tags is not tags

        if PY3:
            assert normalized_tag == tag.decode('utf-8')
        else:
            # Ensure no new allocation occurs
            assert normalized_tag is tag

    def test_unicode_string(self):
        check = AgentCheck()
        tag = u'unicode:string'
        tags = [tag]

        normalized_tags = check._normalize_tags_type(tags, None)
        normalized_tag = normalized_tags[0]

        assert normalized_tags is not tags

        if PY3:
            # Ensure no new allocation occurs
            assert normalized_tag is tag
        else:
            assert normalized_tag == tag.encode('utf-8')

    def test_unicode_device_name(self):
        check = AgentCheck()
        tags = []
        device_name = u'unicode_string'

        normalized_tags = check._normalize_tags_type(tags, device_name)
        normalized_device_tag = normalized_tags[0]

        assert isinstance(normalized_device_tag, str if PY3 else bytes)

    def test_duplicated_device_name(self):
        check = AgentCheck()
        tags = []
        device_name = 'foo'
        check._normalize_tags_type(tags, device_name)
        normalized_tags = check._normalize_tags_type(tags, device_name)
        assert len(normalized_tags) == 1

    def test__to_bytes(self):
        if PY3:
            pytest.skip('Method only exists on Python 2')
        check = AgentCheck()
        assert isinstance(check._to_bytes(b"tag:foo"), bytes)
        assert isinstance(check._to_bytes(u"tag:☣"), bytes)
        in_str = mock.MagicMock(side_effect=Exception)
        in_str.encode.side_effect = Exception
        assert check._to_bytes(in_str) is None


class LimitedCheck(AgentCheck):
    DEFAULT_METRIC_LIMIT = 10


class TestLimits():
    def test_context_uid(self, aggregator):
        check = LimitedCheck()

        # Test stability of the hash against tag ordering
        uid = check._context_uid(aggregator.GAUGE, "test.metric", ["one", "two"], None)
        assert uid == check._context_uid(aggregator.GAUGE, "test.metric", ["one", "two"], None)
        assert uid == check._context_uid(aggregator.GAUGE, "test.metric", ["two", "one"], None)

        # Test all fields impact the hash
        assert uid != check._context_uid(aggregator.RATE, "test.metric", ["one", "two"], None)
        assert uid != check._context_uid(aggregator.GAUGE, "test.metric2", ["one", "two"], None)
        assert uid != check._context_uid(aggregator.GAUGE, "test.metric", ["two"], None)
        assert uid != check._context_uid(aggregator.GAUGE, "test.metric", ["one", "two"], "host")

    def test_metric_limit_gauges(self, aggregator):
        check = LimitedCheck()
        assert check.get_warnings() == []

        for i in range(0, 10):
            check.gauge("metric", 0)
        assert len(check.get_warnings()) == 0
        assert len(aggregator.metrics("metric")) == 10

        for i in range(0, 10):
            check.gauge("metric", 0)
        assert len(check.get_warnings()) == 1
        assert len(aggregator.metrics("metric")) == 10

    def test_metric_limit_count(self, aggregator):
        check = LimitedCheck()
        assert check.get_warnings() == []

        # Multiple calls for a single set of (metric_name, tags) should not trigger
        for i in range(0, 20):
            check.count("metric", 0, hostname="host-single")
        assert len(check.get_warnings()) == 0
        assert len(aggregator.metrics("metric")) == 20

        # Multiple sets of tags should trigger
        # Only 9 new sets of tags should pass through
        for i in range(0, 20):
            check.count("metric", 0, hostname="host-{}".format(i))
        assert len(check.get_warnings()) == 1
        assert len(aggregator.metrics("metric")) == 29

    def test_metric_limit_instance_config(self, aggregator):
        instances = [
            {
                "max_returned_metrics": 42,
            }
        ]
        check = AgentCheck("test", {}, instances)
        assert check.get_warnings() == []

        for i in range(0, 42):
            check.gauge("metric", 0)
        assert len(check.get_warnings()) == 0
        assert len(aggregator.metrics("metric")) == 42

        check.gauge("metric", 0)
        assert len(check.get_warnings()) == 1
        assert len(aggregator.metrics("metric")) == 42

    def test_metric_limit_instance_config_zero(self, aggregator):
        instances = [
            {
                "max_returned_metrics": 0,
            }
        ]
        check = LimitedCheck("test", {}, instances)
        assert len(check.get_warnings()) in [1, 2]

        for i in range(0, 42):
            check.gauge("metric", 0)
        assert len(check.get_warnings()) == 1  # get_warnings resets the array
        assert len(aggregator.metrics("metric")) == 10


class DefaultInstanceCheck(AgentCheck):
    pass


class AgentIntegrationInstanceCheck(AgentCheck):
    def get_instance_key(self, instance):
        return AgentIntegrationInstance("test", "integration")


class TopologyCheck(AgentCheck):
    def __init__(self, key=None, *args, **kwargs):
        super(TopologyCheck, self).__init__(*args, **kwargs)
        self.key = key or TopologyInstance("mytype", "someurl")

    def get_instance_key(self, instance):
        return self.key


class TopologyAutoSnapshotCheck(TopologyCheck):
    def __init__(self):
        instances = [{'a': 'b'}]
        super(TopologyAutoSnapshotCheck, self) \
            .__init__(TopologyInstance("mytype", "someurl", with_snapshots=True), "test", {}, instances)

    def check(self, instance):
        pass


class TopologyBrokenCheck(TopologyAutoSnapshotCheck):
    def __init__(self):
        super(TopologyBrokenCheck, self).__init__()

    def check(self, instance):
        raise Exception("some error in my check")


TEST_STATE = {
    'string': 'string',
    'int': 1,
    'float': 1.0,
    'bool': True,
    'list': ['a', 'b', 'c'],
    'dict': {'a': 'b'}
}


class TopologyStatefulCheck(TopologyAutoSnapshotCheck):
    def __init__(self):
        super(TopologyStatefulCheck, self).__init__()

    @staticmethod
    def get_agent_conf_d_path():
        return "./test_data"

    def check(self, instance):
        instance.update({'state': TEST_STATE})


class TopologyStatefulStateDescriptorCleanupCheck(TopologyAutoSnapshotCheck):
    def __init__(self):
        instances = [{'a': 'b'}]
        super(TopologyAutoSnapshotCheck, self) \
            .__init__(TopologyInstance("mytype", "https://some.type.url", with_snapshots=True), "test", {}, instances)

    @staticmethod
    def get_agent_conf_d_path():
        return "./test_data"

    def check(self, instance):
        instance.update({'state': TEST_STATE})


class TopologyClearStatefulCheck(TopologyStatefulCheck):
    def __init__(self):
        super(TopologyClearStatefulCheck, self).__init__()

    def check(self, instance):
        instance.update({'state': None})


class TopologyBrokenStatefulCheck(TopologyStatefulCheck):
    def __init__(self):
        super(TopologyBrokenStatefulCheck, self).__init__()

    def check(self, instance):
        instance.update({'state': TEST_STATE})

        raise Exception("some error in my check")


class IdentifierMappingTestAgentCheck(TopologyCheck):
    def __init__(self):
        instances = [
            {
                'identifier_mappings':
                    {
                        'host': {'field': 'url', 'prefix': 'urn:computer:/'},
                        'vm': {'field': 'name', 'prefix': 'urn:computer:/'}
                    }
            }
        ]
        super(IdentifierMappingTestAgentCheck, self) \
            .__init__(TopologyInstance("host", "someurl"), "test", {}, instances)

    def check(self, instance):
        pass


class NestedIdentifierMappingTestAgentCheck(TopologyCheck):
    def __init__(self):
        instances = [
            {
                'identifier_mappings':
                    {
                        'host': {'field': 'x.y.z.url', 'prefix': 'urn:computer:/'}
                    }
            }
        ]
        super(NestedIdentifierMappingTestAgentCheck, self) \
            .__init__(TopologyInstance("host", "someurl"), "test", {}, instances)

    def check(self, instance):
        pass


class StateSchema(Model):
    offset = IntType(required=True)


class CheckInstanceSchema(Model):
    a = StringType(required=True)
    state = ModelType(StateSchema, required=True, default=StateSchema({'offset': 0}))


class TopologyStatefulSchemaCheck(TopologyStatefulCheck):
    INSTANCE_SCHEMA = CheckInstanceSchema

    def check(self, instance):
        print(instance.a)
        instance.state.offset = 20


class TagsAndConfigMappingAgentCheck(TopologyCheck):
    def __init__(self, include_instance_config):
        instance = {
            'identifier_mappings': {
                'host': {'field': 'url', 'prefix': 'urn:computer:/'},
                'vm': {'field': 'name', 'prefix': 'urn:computer:/'}
            },
        }

        if include_instance_config:
            instance.update({
                'stackstate-layer': 'instance-stackstate-layer',
                'stackstate-environment': 'instance-stackstate-environment',
                'stackstate-domain': 'instance-stackstate-domain',
                'stackstate-identifiers': 'urn:process:/mapped-identifier:0:1234567890, \
                    urn:process:/mapped-identifier:1:1234567890 \
                    urn:process:/mapped-identifier:2:1234567890  ,  \
                    urn:process:/mapped-identifier:3:1234567890'
            })

        super(TagsAndConfigMappingAgentCheck, self) \
            .__init__(TopologyInstance("host", "someurl"), "test", {}, [instance])

    def check(self, instance):
        pass


class TestTagsAndConfigMapping:
    def generic_tags_and_config_application(self, topology, include_instance_config, include_tags, extra_data=None):
        check = TagsAndConfigMappingAgentCheck(include_instance_config)
        data = {}
        if include_tags:
            data = {
                'tags': ['stackstate-layer:tag-stackstate-layer',
                         'stackstate-environment:tag-stackstate-environment',
                         'stackstate-domain:tag-stackstate-domain',
                         'stackstate-identifiers:\
                             urn:process:/mapped-identifier:0:1234567890, \
                             urn:process:/mapped-identifier:1:1234567890 \
                             urn:process:/mapped-identifier:2:1234567890  ,  \
                             urn:process:/mapped-identifier:3:1234567890'
                         ]
            }
        if extra_data:
            data.update(extra_data)
        check.component("my-id", "host", data)
        return topology.get_snapshot(check.check_id)['components'][0]

    def test_only_instance_config_application(self, topology):
        component = self.generic_tags_and_config_application(topology, True, False)
        assert component["data"]["layer"] == "instance-stackstate-layer"
        assert component["data"]["environment"] == "instance-stackstate-environment"
        assert component["data"]["domain"] == "instance-stackstate-domain"

    def test_only_tags_application(self, topology):
        component = self.generic_tags_and_config_application(topology, False, True)
        assert component["data"]["layer"] == "tag-stackstate-layer"
        assert component["data"]["environment"] == "tag-stackstate-environment"
        assert component["data"]["domain"] == "tag-stackstate-domain"

    def test_tags_overwrite(self, topology):
        component = self.generic_tags_and_config_application(topology, True, True)
        assert component["data"]["layer"] == "tag-stackstate-layer"
        assert component["data"]["environment"] == "tag-stackstate-environment"
        assert component["data"]["domain"] == "tag-stackstate-domain"

    def test_identifier_config_application(self, topology):
        component = self.generic_tags_and_config_application(topology, True, False, {
            'identifiers': ['urn:process:/original-identifier:0:1234567890']
        })
        assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890']

    def test_identifier_tags_application(self, topology):
        component = self.generic_tags_and_config_application(topology, True, True, {
            'identifiers': [
                'urn:process:/original-identifier:0:1234567890'
            ]
        })
        assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890',
                                                    'urn:process:/mapped-identifier:0:1234567890',
                                                    'urn:process:/mapped-identifier:1:1234567890',
                                                    'urn:process:/mapped-identifier:2:1234567890',
                                                    'urn:process:/mapped-identifier:3:1234567890']

class TestTopology:
    def test_component(self, topology):
        check = TopologyCheck()
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        check.component("my-id", "my-type", data)
        topology.assert_snapshot(check.check_id, check.key, components=[component("my-id", "my-type", data)])

    def test_relation(self, topology):
        check = TopologyCheck()
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        check.relation("source-id", "target-id", "my-type", data)
        topology.assert_snapshot(check.check_id, check.key,
                                 relations=[relation("source-id", "target-id", "my-type", data)])

    def test_auto_snapshotting(self, topology):
        check = TopologyAutoSnapshotCheck()
        check.run()
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_no_stop_snapshot_on_exception(self, topology):
        check = TopologyBrokenCheck()
        check.run()
        # assert stop snapshot is false when an exception is thrown in check.run()
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=False)

    def test_start_snapshot(self, topology):
        check = TopologyCheck()
        check.start_snapshot()
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True)

    def test_stop_snapshot(self, topology):
        check = TopologyCheck()
        check.stop_snapshot()
        topology.assert_snapshot(check.check_id, check.key, stop_snapshot=True)

    def test_stateful_check(self, topology, state):
        check = TopologyStatefulCheck()
        state.assert_state_check(check, expected_pre_run_state=None, expected_post_run_state=TEST_STATE)
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_stateful_state_descriptor_cleanup_check(self, topology, state):
        check = TopologyStatefulStateDescriptorCleanupCheck()
        state_descriptor = check._get_state_descriptor()
        assert state_descriptor.instance_key == "instance.mytype.https_some.type.url"
        assert check._get_instance_key_dict() == {'type': 'mytype', 'url': 'https://some.type.url'}
        state.assert_state_check(check, expected_pre_run_state=None, expected_post_run_state=TEST_STATE)
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_clear_stateful_check(self, topology, state):
        check = TopologyClearStatefulCheck()
        # set the previous state and assert the state check function as expected
        check.state_manager.set_state(check._get_state_descriptor(), TEST_STATE)
        state.assert_state_check(check, expected_pre_run_state=TEST_STATE, expected_post_run_state=None)
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_no_state_change_on_exception_stateful_check(self, topology, state):
        check = TopologyBrokenStatefulCheck()
        # set the previous state and assert the state check function as expected
        previous_state = {'my_old': 'state'}
        check.state_manager.set_state(check._get_state_descriptor(), previous_state)
        state.assert_state_check(check, expected_pre_run_state=previous_state, expected_post_run_state=previous_state)
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=False)

    def test_stateful_schema_check(self, topology, state):
        check = TopologyStatefulSchemaCheck()
        # assert the state check function as expected
        state.assert_state_check(check, expected_pre_run_state=None,
                                 expected_post_run_state=StateSchema({'offset': 20}), state_schema=StateSchema)
        # assert auto snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_none_data_ok(self, topology):
        check = TopologyCheck()
        check.component("my-id", "my-type", None)
        topology.assert_snapshot(check.check_id, check.key, components=[component("my-id", "my-type",
                                                                                  {'tags': ['integration-type:mytype',
                                                                                            'integration-url:someurl']
                                                                                   })])

    def test_illegal_data(self):
        check = TopologyCheck()
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", 1)
        if PY3:
            assert str(e.value) == "Got unexpected <class 'int'> for argument data, expected dictionary or None value"
        else:
            assert str(e.value) == "Got unexpected <type 'int'> for argument data, expected dictionary or None value"

    def test_illegal_data_value(self):
        check = TopologyCheck()
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", {"key": set()})
        if PY3:
            assert str(e.value) == """Got unexpected <class 'set'> for argument data.key, \
expected string, int, dictionary, list or None value"""
        else:
            assert str(e.value) == """Got unexpected <type 'set'> for argument data.key, \
expected string, int, dictionary, list or None value"""

    def test_illegal_instance_key_none(self):
        check = TopologyCheck()
        check.key = None
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", None)
        if PY3:
            assert str(e.value) == "Got unexpected <class 'str'> for argument get_instance_key(), expected dictionary"
        else:
            assert str(e.value) == "Got unexpected <type 'str'> for argument get_instance_key(), expected dictionary"

    def test_illegal_instance_type(self):
        check = TopologyCheck()
        check.key = {}
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", None)
        if PY3:
            assert str(e.value) == """Got unexpected <class 'dict'> for argument get_instance_key(), \
expected TopologyInstance, AgentIntegrationInstance or DefaultIntegrationInstance"""
        else:
            assert str(e.value) == """Got unexpected <type 'dict'> for argument get_instance_key(), \
expected TopologyInstance, AgentIntegrationInstance or DefaultIntegrationInstance"""

    def test_illegal_instance_key_field_type(self):
        check = TopologyCheck()
        check.key = TopologyInstance("mytype", 1)
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", None)
        assert str(e.value) == "Instance requires a 'url' field of type 'string'"

    def test_topology_instance(self, topology):
        check = TopologyCheck()
        check.key = TopologyInstance("mytype", "myurl")
        assert check._get_instance_key_dict() == {"type": "mytype", "url": "myurl"}
        check.create_integration_instance()
        # assert integration topology is created for topology instances
        topo_instances = topology.get_snapshot('mytype:myurl')
        assert topo_instances == self.agent_integration_topology('mytype', 'myurl')

    def test_agent_integration_instance(self, topology):
        check = AgentIntegrationInstanceCheck()
        assert check._get_instance_key_dict() == {"type": "agent", "url": "integrations"}
        check.create_integration_instance()
        # assert integration topology is created for agent integration instances
        topo_instances = topology.get_snapshot(check.check_id)
        assert topo_instances == self.agent_integration_topology('test', 'integration')

    def test_agent_telemetry_instance(self, topology):
        check = DefaultInstanceCheck()
        assert check._get_instance_key_dict() == {"type": "agent", "url": "integrations"}
        check.create_integration_instance()
        # assert no integration topology is created for default instances
        assert topology._snapshots == {}

    def agent_integration_topology(self, type, url):
        return {
            'components': [
                {
                    'data': {
                        'cluster': 'stubbed-cluster-name',
                        'hostname': 'stubbed.hostname',
                        'identifiers': [
                            'urn:process:/stubbed.hostname:1:1234567890'
                        ],
                        'name': 'StackState Agent:stubbed.hostname',
                        'tags': sorted([
                            'hostname:stubbed.hostname',
                            'stackstate-agent',
                        ])
                    },
                    'id': 'urn:stackstate-agent:/stubbed.hostname',
                    'type': 'stackstate-agent'
                },
                {
                    'data': {
                        'checks': [
                            {
                                'is_service_check_health_check': True,
                                'name': 'Integration Health',
                                'stream_id': -1
                            }
                        ],
                        'cluster': 'stubbed-cluster-name',
                        'service_checks': [
                            {
                                'conditions': [
                                    {
                                        'key': 'host',
                                        'value': 'stubbed.hostname'
                                    },
                                    {
                                        'key': 'tags.integration-type',
                                        'value': type
                                    }
                                ],
                                'name': 'Service Checks',
                                'stream_id': -1
                            }
                        ],
                        'hostname': 'stubbed.hostname',
                        'integration': type,
                        'name': 'stubbed.hostname:%s' % type,
                        'tags': sorted([
                            'hostname:stubbed.hostname',
                            'integration-type:%s' % type,
                        ])
                    },
                    'id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
                    'type': 'agent-integration'
                },
                {
                    'data': {
                        'checks': [
                            {
                                'is_service_check_health_check': True,
                                'name': 'Integration Instance Health',
                                'stream_id': -1
                            }
                        ],
                        'cluster': 'stubbed-cluster-name',
                        'service_checks': [
                            {
                                'conditions': [
                                    {
                                        'key': 'host',
                                        'value': 'stubbed.hostname'
                                    },
                                    {
                                        'key': 'tags.integration-type',
                                        'value': type
                                    },
                                    {
                                        'key': 'tags.integration-url',
                                        'value': url
                                    }
                                ],
                                'name': 'Service Checks',
                                'stream_id': -1
                            }
                        ],
                        'hostname': 'stubbed.hostname',
                        'integration': type,
                        'name': '%s:%s' % (type, url),
                        'tags': sorted([
                            'hostname:stubbed.hostname',
                            'integration-type:%s' % type,
                            'integration-url:%s' % url
                        ])
                    },
                    'id': 'urn:agent-integration-instance:/stubbed.hostname:%s:%s' % (type, url),
                    'type': 'agent-integration-instance'
                },
            ],
            'instance_key': {
                'type': 'agent',
                'url': 'integrations'
            },
            'relations': [
                {
                    'data': {},
                    'source_id': 'urn:stackstate-agent:/stubbed.hostname',
                    'target_id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
                    'type': 'runs'
                },
                {
                    'data': {},
                    'source_id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
                    'target_id': 'urn:agent-integration-instance:/stubbed.hostname:%s:%s' % (type, url),
                    'type': 'has'
                },
            ],
            'start_snapshot': False,
            'stop_snapshot': False
        }

    def test_component_with_identifier_mapping(self, topology):
        """
        Test should generate identifier mapping based on the prefix and field value
        """
        check = IdentifierMappingTestAgentCheck()
        data = {"url": "identifier-url", "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        check.component("my-id", "host", data)
        component = topology.get_snapshot(check.check_id)['components'][0]
        # there should be only one identifier mapped for host because only `host` type exist
        assert component["data"]["identifiers"] == ["urn:computer:/identifier-url"]

    def test_component_with_identifier_mapping_with_existing_identifier(self, topology):
        """
        Test should generate identifier mapping based on the prefix and field value with extra identifier
        """
        check = IdentifierMappingTestAgentCheck()
        data = {"url": "identifier-url", "identifiers": ["urn:host:/host-1"],
                "nestedobject": {"nestedkey": "nestedValue"}}
        check.component("my-id", "host", data)
        component = topology.get_snapshot(check.check_id)['components'][0]
        # there should be 2 identifier mapped for host because there was an existing identifier
        assert component["data"]["identifiers"] == ["urn:host:/host-1", "urn:computer:/identifier-url"]

    def test_component_identifier_mapping_with_no_field(self, topology):
        """
        Test should not generate identifier mapping because field value doesn't exist in data
        """
        check = IdentifierMappingTestAgentCheck()
        data = {"emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        check.component("my-id", "host", data)
        component = topology.get_snapshot(check.check_id)['components'][0]
        # there should be no identifier mapped for host because field value `url` doesn't exist in data
        assert component["data"].get("identifiers") is None

    def test_component_identifier_mapping_with_nested_field(self, topology):
        """
        Test should generate identifier mapping because based on the prefix and nested field value
        """
        check = NestedIdentifierMappingTestAgentCheck()
        data = {"emptykey": None, "x": {"y": {"z": {"url": "identifier-url"}}}}
        check.component("my-id", "host", data)
        component = topology.get_snapshot(check.check_id)['components'][0]
        # there should be one identifier mapped for host because only `host` type exist on the nested field
        assert component["data"]["identifiers"] == ["urn:computer:/identifier-url"]

    def test_component_nested_identifier_mapping_with_no_field(self, topology):
        """
        Test should not generate identifier mapping because nested field value doesn't exist in data
        """
        check = NestedIdentifierMappingTestAgentCheck()
        data = {"emptykey": None}
        check.component("my-id", "host", data)
        component = topology.get_snapshot(check.check_id)['components'][0]
        # there should be no identifier mapped for host because field value `x.y.z.url` doesn't exist in data
        assert component["data"].get("identifiers") is None
