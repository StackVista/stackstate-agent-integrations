# -*- coding: utf-8 -*-

# (C) StackState, Inc. 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import copy
import json
import mock
import pytest
import sys

from six import PY3, text_type
from schematics import Model
from schematics.exceptions import ValidationError, ConversionError, DataError
from schematics.types import URLType, ListType, StringType, IntType, ModelType
from stackstate_checks.checks import AgentCheckV2, TransactionalAgentCheck, StatefulAgentCheck, StackPackInstance, \
    TopologyInstance, AgentIntegrationInstance, HealthStream, HealthStreamUrn, Health
from stackstate_checks.base.stubs import datadog_agent
from stackstate_checks.base.stubs.topology import component
from stackstate_checks.base.utils.state_api import generate_state_key


TEST_INSTANCE = {
    "url": "https://example.org/api"
}


def test_instance():
    """
    Simply assert the class can be instantiated
    """
    AgentCheckV2()
    # rely on default
    check = AgentCheckV2()
    assert check.init_config == {}
    assert check.instances == []

    # pass dict for 'init_config', a list for 'instances'
    init_config = {'foo': 'bar'}
    instances = [{'bar': 'baz'}]
    check = AgentCheckV2(init_config=init_config, instances=instances)
    assert check.init_config == {'foo': 'bar'}
    assert check.instances == [{'bar': 'baz'}]


def test_load_config():
    assert AgentCheckV2.load_config("raw_foo: bar") == {'raw_foo': 'bar'}


def test_log_critical_error():
    check = AgentCheckV2()

    with pytest.raises(NotImplementedError):
        check.log.critical('test')


class TestMetricNormalization:
    def test_default(self):
        check = AgentCheckV2()
        metric_name = u'Klüft inför på fédéral'
        normalized_metric_name = b'Kluft_infor_pa_federal'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_fix_case(self):
        check = AgentCheckV2()
        metric_name = u'Klüft inför på fédéral'
        normalized_metric_name = b'kluft_infor_pa_federal'

        assert check.normalize(metric_name, fix_case=True) == normalized_metric_name

    def test_prefix(self):
        check = AgentCheckV2()
        metric_name = u'metric'
        prefix = u'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_prefix_bytes(self):
        check = AgentCheckV2()
        metric_name = u'metric'
        prefix = b'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_prefix_unicode_metric_bytes(self):
        check = AgentCheckV2()
        metric_name = b'metric'
        prefix = u'some'
        normalized_metric_name = b'some.metric'

        assert check.normalize(metric_name, prefix=prefix) == normalized_metric_name

    def test_underscores_redundant(self):
        check = AgentCheckV2()
        metric_name = u'a_few__redundant___underscores'
        normalized_metric_name = b'a_few_redundant_underscores'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_underscores_at_ends(self):
        check = AgentCheckV2()
        metric_name = u'_some_underscores_'
        normalized_metric_name = b'some_underscores'

        assert check.normalize(metric_name) == normalized_metric_name

    def test_underscores_and_dots(self):
        check = AgentCheckV2()
        metric_name = u'some_.dots._and_._underscores'
        normalized_metric_name = b'some.dots.and.underscores'

        assert check.normalize(metric_name) == normalized_metric_name


class TestMetrics:
    def test_non_float_metric(self, aggregator):
        check = AgentCheckV2()
        metric_name = 'test_metric'
        with pytest.raises(ValueError):
            check.gauge(metric_name, '85k')
        aggregator.assert_metric(metric_name, count=0)


class TestEvents:
    def test_valid_event(self, aggregator):
        check = AgentCheckV2()
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
        # del tags, the base check drops None
        del event['tags']
        aggregator.assert_event('test event test event')

    def test_topology_event(self, telemetry):
        check = AgentCheckV2()
        event = {
            "timestamp": 123456789,
            "source_type_name": "new.source.type",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": [],
            "context": {
                "element_identifiers": ["urn:test:/value"],
                "source": "test source",
                "category": "test category",
            }
        }
        check.event(event)
        # event_type key and value should be generated by event method
        expected_event = event.copy()
        expected_event["event_type"] = "new.source.type"
        telemetry.assert_topology_event(expected_event)


class TestServiceChecks:
    def test_valid_sc(self, aggregator):
        check = AgentCheckV2()

        check.service_check("testservicecheck", AgentCheckV2.OK, tags=None, message="")
        aggregator.assert_service_check("testservicecheck", status=AgentCheckV2.OK)

        check.service_check("testservicecheckwithhostname", AgentCheckV2.OK, tags=["foo", "bar"], hostname="testhostname",
                            message="a message")
        aggregator.assert_service_check("testservicecheckwithhostname", status=AgentCheckV2.OK, tags=["foo", "bar"],
                                        hostname="testhostname", message="a message")

        check.service_check("testservicecheckwithnonemessage", AgentCheckV2.OK, message=None)
        aggregator.assert_service_check("testservicecheckwithnonemessage", status=AgentCheckV2.OK, )


class TestTags:
    def test_default_string(self):
        check = AgentCheckV2()
        tag = 'default:string'
        tags = [tag]

        normalized_tags = check._normalize_tags_type(tags, None)
        normalized_tag = normalized_tags[0]

        assert normalized_tags is not tags
        # Ensure no new allocation occurs
        assert normalized_tag is tag

    def test_bytes_string(self):
        check = AgentCheckV2()
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
        check = AgentCheckV2()
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
        check = AgentCheckV2()
        tags = []
        device_name = u'unicode_string'

        normalized_tags = check._normalize_tags_type(tags, device_name)
        normalized_device_tag = normalized_tags[0]

        assert isinstance(normalized_device_tag, str if PY3 else bytes)

    def test_duplicated_device_name(self):
        check = AgentCheckV2()
        tags = []
        device_name = 'foo'
        check._normalize_tags_type(tags, device_name)
        normalized_tags = check._normalize_tags_type(tags, device_name)
        assert len(normalized_tags) == 1

    def test__to_bytes(self):
        if PY3:
            pytest.skip('Method only exists on Python 2')
        check = AgentCheckV2()
        assert isinstance(check._to_bytes(b"tag:foo"), bytes)
        assert isinstance(check._to_bytes(u"tag:☣"), bytes)
        in_str = mock.MagicMock(side_effect=UnicodeError)
        in_str.encode.side_effect = UnicodeError
        assert check._to_bytes(in_str) is None


class LimitedCheck(AgentCheckV2):
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
        check = AgentCheckV2("test", {}, instances)
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


class DefaultInstanceCheck(AgentCheckV2):
    def check(self, instance):
        pass


class AgentIntegrationInstanceCheck(AgentCheckV2):
    def get_instance_key(self, instance):
        return AgentIntegrationInstance("test", "integration")

    def check(self, instance):
        pass


class TopologyCheck(AgentCheckV2):
    def __init__(self, key=None, *args, **kwargs):
        super(TopologyCheck, self).__init__(*args, **kwargs)
        self.key = key or TopologyInstance("mytype", "someurl")

    def get_instance_key(self, instance):
        return self.key

    def check(self, instance):
        pass


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


class HealthCheck(AgentCheckV2):
    def __init__(self,
                 stream=HealthStream(HealthStreamUrn("source", "stream_id"), "sub_stream"),
                 instance={'collection_interval': 15, 'a': 'b'},
                 *args, **kwargs):
        instances = [instance]
        self.stream = stream
        super(HealthCheck, self).__init__("test", {}, instances)

    def get_health_stream(self, instance):
        return self.stream

    def check(self, instance):
        return


class HealthCheckMainStream(AgentCheckV2):
    def __init__(self, stream=HealthStream(HealthStreamUrn("source", "stream_id")), *args, **kwargs):
        instances = [{'collection_interval': 15, 'a': 'b'}]
        self.stream = stream
        super(HealthCheckMainStream, self).__init__("test", {}, instances)

    def get_health_stream(self, instance):
        return self.stream

    def check(self, instance):
        return


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
                'stackstate-identifier': 'instance-stackstate-identifier',
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
    def generic_tags_and_config_snapshot(self, topology, include_instance_config, include_tags, extra_data=None):
        check = TagsAndConfigMappingAgentCheck(include_instance_config)
        data = {}
        if include_tags:
            data = {
                'tags': ['stackstate-layer:tag-stackstate-layer',
                         'stackstate-environment:tag-stackstate-environment',
                         'stackstate-domain:tag-stackstate-domain',
                         'stackstate-identifier:urn:process:/mapped-identifier:001:1234567890',
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

    def test_comma_and_spaces_regex(self):
        check = TagsAndConfigMappingAgentCheck(True)
        assert check.split_on_commas_and_spaces('a, b, c,d,e f g h, i , j ,k   ') == \
               ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
        assert check.split_on_commas_and_spaces('a,  ,  ,, , j ,k   ') == ["a", "j", "k"]
        assert check.split_on_commas_and_spaces(',,,,,,,,,,,           ,,,,,,,,,') == []
        assert check.split_on_commas_and_spaces('') == []
        assert check.split_on_commas_and_spaces('urn:test:0:123,urn:test:1:123,urn:test:2:123') == \
               ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]
        assert check.split_on_commas_and_spaces('urn:test:0:123 urn:test:1:123 urn:test:2:123') == \
               ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]
        assert check.split_on_commas_and_spaces('urn:test:0:123 urn:test:1:123,urn:test:2:123') == \
               ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]

    def test_mapping_config_and_tags(self):
        # We are create config variables with and without instance config
        check_include_config = TagsAndConfigMappingAgentCheck(True)
        check_exclude_config = TagsAndConfigMappingAgentCheck(False)

        """
            We are testing the following:
                Config + No Data == Config Result is not in a Array
                Config + No Data, True == Config Result is in a Array
                Config + Data == Data Result is not in a Array (Must not be config)
                Config + Data, True == Data Result is in a Array (Must not be config)
                No Config + No Data + Default Value == Result must be the default value and not a Array
                No Config + No Data + Default Value, True == Result must be the default value in a Array
            Tags must overwrite configs
        """

        def generic_mapping_test(target, origin, default_value=None):
            data = {
                'tags': ['stackstate-layer:tag-stackstate-layer',
                         'stackstate-environment:tag-stackstate-environment',
                         'stackstate-domain:tag-stackstate-domain',
                         'stackstate-identifier:tag-stackstate-identifier',
                         'stackstate-identifiers:tag-stackstate-identifiers']
            }

            # Create a copy of the data object
            data_without_target = copy.deepcopy(data)

            # Remove the current target from the tags array as the result should not contain that tag
            data_without_target.get("tags").remove(target + ":tag-" + target)

            # Include instance config in the tests
            assert check_include_config._move_data_with_config_or_tags({}, target, origin) == \
                   {origin: 'instance-' + target}
            assert check_include_config._move_data_with_config_or_tags({}, target, origin, True) == \
                   {origin: ['instance-' + target]}
            assert check_include_config._move_data_with_config_or_tags(copy.deepcopy(data), target, origin) == \
                   {origin: 'tag-' + target, 'tags': data_without_target['tags']}
            assert check_include_config._move_data_with_config_or_tags(copy.deepcopy(data), target, origin, True) == \
                   {origin: ['tag-' + target], 'tags': data_without_target['tags']}

            # Exclude the instance config in the tests
            assert check_exclude_config._move_data_with_config_or_tags({}, target, origin) == {}
            assert check_exclude_config._move_data_with_config_or_tags({}, target, origin, True) == {}
            assert check_exclude_config._move_data_with_config_or_tags(copy.deepcopy(data), target, origin) == \
                   {origin: 'tag-' + target, 'tags': data_without_target['tags']}
            assert check_exclude_config._move_data_with_config_or_tags(copy.deepcopy(data), target, origin, True) == \
                   {origin: ['tag-' + target], 'tags': data_without_target['tags']}

            # Default Config
            assert check_exclude_config._move_data_with_config_or_tags({}, target, origin, False, default_value) == \
                   {origin: default_value}
            assert check_exclude_config._move_data_with_config_or_tags({}, target, origin, True, default_value) == \
                   {origin: [default_value]}

            # Return direct value & Return direct value arrays test
            assert check_exclude_config._get_config_or_tag_value(copy.deepcopy(data), target, False) == \
                   'tag-' + target
            assert check_include_config._get_config_or_tag_value(copy.deepcopy(data), target, False) == \
                   'tag-' + target
            assert check_exclude_config._get_config_or_tag_value({}, target, False) is None
            assert check_include_config._get_config_or_tag_value({}, target, False) == \
                   'instance-' + target
            assert check_exclude_config._get_config_or_tag_value(copy.deepcopy(data), target, True) == \
                   ['tag-' + target]
            assert check_include_config._get_config_or_tag_value(copy.deepcopy(data), target, True) == \
                   ['tag-' + target]
            assert check_exclude_config._get_config_or_tag_value({}, target, True) == \
                   []
            assert check_include_config._get_config_or_tag_value({}, target, True) == \
                   ['instance-' + target]

        # We are testing the environment, layer and domain for all the use cases
        generic_mapping_test("stackstate-environment", "environments", "default-environment")
        generic_mapping_test("stackstate-layer", "layer", "default-layer")
        generic_mapping_test("stackstate-domain", "domain", "default-domain")
        generic_mapping_test("stackstate-identifier", "identifier", "default-identifier")

    def test_instance_only_config(self, topology):
        component = self.generic_tags_and_config_snapshot(topology, True, False)
        assert component["data"]["layer"] == "instance-stackstate-layer"
        assert component["data"]["environments"] == ["instance-stackstate-environment"]
        assert component["data"]["domain"] == "instance-stackstate-domain"

    def test_tags_only(self, topology):
        component = self.generic_tags_and_config_snapshot(topology, False, True)
        assert component["data"]["layer"] == "tag-stackstate-layer"
        assert component["data"]["environments"] == ["tag-stackstate-environment"]
        assert component["data"]["domain"] == "tag-stackstate-domain"

    def test_tags_overwrite_config(self, topology):
        component = self.generic_tags_and_config_snapshot(topology, True, True)
        assert component["data"]["layer"] == "tag-stackstate-layer"
        assert component["data"]["environments"] == ["tag-stackstate-environment"]
        assert component["data"]["domain"] == "tag-stackstate-domain"

    def test_identifier_config(self, topology):
        component = self.generic_tags_and_config_snapshot(topology, True, False, {
            'identifiers': ['urn:process:/original-identifier:0:1234567890']
        })
        assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890',
                                                    'instance-stackstate-identifier']

    def test_identifier_tags(self, topology):
        component = self.generic_tags_and_config_snapshot(topology, True, True, {
            'identifiers': [
                'urn:process:/original-identifier:0:1234567890'
            ],
            'url': '1234567890'
        })
        assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890',
                                                    'urn:computer:/1234567890',
                                                    'urn:process:/mapped-identifier:0:1234567890',
                                                    'urn:process:/mapped-identifier:1:1234567890',
                                                    'urn:process:/mapped-identifier:2:1234567890',
                                                    'urn:process:/mapped-identifier:3:1234567890',
                                                    'urn:process:/mapped-identifier:001:1234567890']


class TestBaseSanitize:
    def test_ensure_homogeneous_list(self):
        """
        Testing the functionality of _ensure_homogeneous_list to ensure that agent checks can only produce homogeneous
        lists
        """
        check = AgentCheckV2()

        # list of ints
        check._ensure_homogeneous_list([1, 2, 3])
        # list of booleans
        check._ensure_homogeneous_list([True, True, False])
        # list of string
        check._ensure_homogeneous_list(['a', 'b', 'c'])
        # list of string + text_type
        check._ensure_homogeneous_list(['a', u'b', '®'])
        # list of floats
        check._ensure_homogeneous_list([1.0, 2.0, 3.0])
        # list of dicts
        check._ensure_homogeneous_list([{'a': 'b'}, {'a': 'c'}, {'a': 'd'}])
        # list of mixed dicts
        check._ensure_homogeneous_list([{'a': 'b'}, {'c': []}, {'d': False}])
        # list of lists
        check._ensure_homogeneous_list([[1], [2], [3]])
        # list of mixed lists
        check._ensure_homogeneous_list([[1], ['b'], [True], [{'c': 'd'}]])
        # list of sets
        check._ensure_homogeneous_list([set([1]), set([2]), set([3])])
        # list of mixed sets
        check._ensure_homogeneous_list([set([1]), set(['b']), set([True]), set([1.5])])

        def exeception_case(list, expected_types):
            with pytest.raises(TypeError) as e:
                check._ensure_homogeneous_list(list)

            assert str(e.value) == "List: {0}, is not homogeneous, it contains the following types: {1}" \
                .format(list, expected_types)

        # list of ints and strings
        exeception_case([1, '2', 3, '4'], {str, int})
        # list of int, string, float, bool
        exeception_case([1, '2', 3.5, True], {str, int, float, bool})
        # list of ints and floats
        exeception_case([1, 1.5, 2, 2.5], {int, float})
        # list of ints and bools
        exeception_case([1, True, 2, False], {int, bool})
        # list of ints and dicts
        exeception_case([1, {'a': True}, 2, {'a': False}], {int, dict})
        # list of strings and lists
        exeception_case(['a', [True], 'b', [False]], {str, list})
        # list of strings and sets
        exeception_case(['a', set([True]), 'b', set([False])], {str, set})
        # list of strings, sets and dicts
        exeception_case(['a', set([True]), {'a': True}, 'b', set([False])], {str, set, dict})

        # list of strings and dicts
        exeception_case(['a', {'a': True}, 'b', {'a': False}], {str, dict})
        # list of strings and floats
        exeception_case(['a', 1.5, 'b', 2.5], {str, float})
        # list of strings and bools
        exeception_case(['a', True, 'b', False], {str, bool})
        # list of strings and lists
        exeception_case(['a', [True], 'b', [False]], {str, list})
        # list of strings and sets
        exeception_case(['a', set([True]), 'b', set([False])], {str, set})

        # list of lists and dicts
        exeception_case([['a'], {'a': True}, ['b'], {'a': False}], {list, dict})
        # list of lists and sets
        exeception_case([['a'], set(['a']), ['b'], set(['b'])], {list, set})

    def test_ensure_homogeneous_list_check_api(self):
        """
        Testing the functionality of _ensure_homogeneous_list, but we're calling it through the check api to ensure that
        topology and telemetry is not created when the data contains a non-homogeneous list
        """
        check = AgentCheckV2()

        # ensure nothing is created for components with non-homogeneous lists
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
                "mixedlist": ['a', 'b', 'c', 4]}
        assert check.component("my-id", "my-type", data) is None
        # ensure nothing is created for relations with non-homogeneous lists
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
                "mixedlist": ['a', 'b', 'c', 4]}
        assert check.relation("source-id", "target-id", "my-type", data) is None
        # ensure that a schematics data error is thrown for events with non-homogeneous tags
        with pytest.raises(DataError):
            event = {
                "timestamp": 123456789,
                "event_type": "new.event",
                "source_type_name": "new.source.type",
                "msg_title": "new test event",
                "aggregation_key": "test.event",
                "msg_text": "test event test event",
                "tags": ['a', 'b', 'c', 4],
            }
            assert check.event(event) is None
        # ensure that a schematics data error is thrown for topology events with non-homogeneous tags
        with pytest.raises(DataError):
            event = {
                "timestamp": 123456789,
                "source_type_name": "new.source.type",
                "msg_title": "new test event",
                "aggregation_key": "test.event",
                "msg_text": "test event test event",
                "tags": ['a', 'b', 'c', 4],
                "context": {
                    "element_identifiers": ["urn:test:/value"],
                    "source": "test source",
                    "category": "test category",
                }
            }
            assert check.event(event) is None
        # ensure that a nothing is created for topology events with non-homogeneous tags in the data section
        event = {
            "timestamp": 123456789,
            "source_type_name": "new.source.type",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": ['a', 'b', 'c', 'd'],
            "context": {
                "element_identifiers": ["urn:test:/value"],
                "source": "test source",
                "category": "test category",
                "data": {
                    "mixedlist": ['a', 'b', 'c', 4]
                }
            }
        }
        assert check.event(event) is None

    @pytest.mark.skipif(sys.platform.startswith('win') and sys.version_info < (3, 7),
                        reason='ordered set causes erratic error failures on windows')
    def test_ensure_string_only_keys(self):
        """
        Testing the functionality of _ensure_string_only_keys, but we're calling _sanitize to deal with multi-tier
        dictionaries
        """
        check = AgentCheckV2()

        # valid dictionaries
        check._sanitize({'a': 1, 'c': True, 'e': 'f'})
        check._sanitize({'a': {'b': {'c': True}}, 'e': 1.2})
        check._sanitize({'a': {'b': {'c': {'e': ['f', 'g']}}}})

        def exeception_case(dictionary, error_type_set):
            with pytest.raises(TypeError) as e:
                check._sanitize(dictionary)

            assert "contains keys which are not string or {0}: {1}".format(text_type, error_type_set) in str(e.value)

        # dictionary with int as keys
        exeception_case({'a': 'b', 'c': 'd', 1: 'f'}, {str, int})
        exeception_case({'a': {'b': {1: 'd'}}, 'e': 'f'}, {int})  # inner dictionary only has a int key
        exeception_case({'a': {'b': {'c': {1: 'f'}}}}, {int})  # inner dictionary only has a int key
        # dictionary with None as keys
        exeception_case({'a': 'b', 'c': 'd', None: 'f'}, {str, type(None)})
        exeception_case({'a': {'b': {None: 'd'}}, 'e': 'f'}, {type(None)})  # inner dictionary only has a None key
        exeception_case({'a': {'b': {'c': {None: 'f'}}}}, {type(None)})  # inner dictionary only has a None key
        # dictionary with list as keys
        exeception_case({'a': 'b', 'c': 'd', True: 'f'}, {str, bool})
        exeception_case({'a': {'b': {True: 'd'}}, 'e': 'f'}, {bool})  # inner dictionary only has a bool key
        exeception_case({'a': {'b': {'c': {True: 'f'}}}}, {bool})  # inner dictionary only has a bool key

    def test_ensure_string_only_keys_check_functions(self):
        """
        Testing the functionality of _ensure_string_only_keys, but we're calling it through the check api to ensure that
        topology and telemetry is not created when a dictionary contains a non-string key
        """
        check = AgentCheckV2()
        # ensure nothing is created for components with non-string key dicts
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
                "nonstringkeydict": {'a': 'b', 3: 'c'}}
        assert check.component("my-id", "my-type", data) is None
        # ensure nothing is created for relations with non-string key dicts
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
                "nonstringkeydict": {'a': 'b', 3: 'c'}}
        assert check.relation("source-id", "target-id", "my-type", data) is None
        # ensure that a nothing is created for topology events with non-string key dicts in the data section
        event = {
            "timestamp": 123456789,
            "source_type_name": "new.source.type",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": ['a', 'b', 'c', 'd'],
            "context": {
                "element_identifiers": ["urn:test:/value"],
                "source": "test source",
                "category": "test category",
                "data": {"nonstringkeydict": {'a': 'b', 3: 'c'}}
            }
        }
        assert check.event(event) is None


class TestTopology:
    def test_component(self, topology):
        check = TopologyCheck()
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        created_component = check.component("my-id", "my-type", data)
        assert data['key'] == created_component['data']['key']
        assert data['intlist'] == created_component['data']['intlist']
        assert data['nestedobject'] == created_component['data']['nestedobject']
        assert created_component['id'] == 'my-id'
        assert created_component['type'] == 'my-type'
        topology.assert_snapshot(check.check_id, check.key, components=[created_component])

    def test_relation(self, topology):
        check = TopologyCheck()
        data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        created_relation = check.relation("source-id", "target-id", "my-type", data)
        assert data['key'] == created_relation['data']['key']
        assert data['intlist'] == created_relation['data']['intlist']
        assert data['nestedobject'] == created_relation['data']['nestedobject']
        assert created_relation['source_id'] == 'source-id'
        assert created_relation['target_id'] == 'target-id'
        assert created_relation['type'] == 'my-type'
        topology.assert_snapshot(check.check_id, check.key, relations=[created_relation])

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
            assert check.component("my-id", "my-type", {"key": {1, 2, 3}})
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
            'delete_ids': [],
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

    def test_delete(self, topology):
        """
        Test checks collection component/relation identifier marked for deletion.
        """
        check = TopologyCheck()
        deleted_component = check.delete("my-id")
        topology.assert_snapshot(check.check_id, check.key, delete_ids=[deleted_component])


class TestHealthStreamUrn:
    def test_health_stream_urn_escaping(self):
        urn = HealthStreamUrn("source.", "stream_id:")
        assert urn.urn_string() == "urn:health:source.:stream_id%3A"

    def test_verify_types(self):
        with pytest.raises(ConversionError) as e:
            HealthStreamUrn(None, "stream_id")
        assert e.value[0] == "This field is required."

        with pytest.raises(ConversionError) as e2:
            HealthStreamUrn("source", None)
        assert e2.value[0] == "This field is required."


class TestHealthStream:
    def test_throws_error_when_expiry_on_sub_stream(self):
        with pytest.raises(ValueError) as e:
            HealthStream(HealthStreamUrn("source.", "stream_id:"), "sub_stream", expiry_seconds=0)
        assert str(e.value) == "Expiry cannot be disabled if a substream is specified"

    def test_verify_types(self):
        with pytest.raises(ValidationError) as e:
            HealthStream("str")
        assert e.value[0] == "Value must be of class: <class 'stackstate_checks.base.utils.health_api.HealthStreamUrn'>"

        with pytest.raises(ValidationError) as e:
            HealthStream(HealthStreamUrn("source", "urn"), sub_stream=1)
        assert e.value[0] == """Value must be a string"""

        with pytest.raises(ConversionError) as e:
            HealthStream(HealthStreamUrn("source", "urn"), repeat_interval_seconds="")
        assert e.value[0].summary == "Value '' is not int."

        with pytest.raises(ConversionError) as e:
            HealthStream(HealthStreamUrn("source", "urn"), expiry_seconds="")
        assert e.value[0].summary == "Value '' is not int."


class TestHealth:
    def test_check_state_max_values(self, health):
        # Max values: fill in as much of the optional fields as possible
        check = HealthCheck()
        check._init_health_api()
        check.health.check_state("check_id", "name", Health.CRITICAL, "identifier", "message")
        health.assert_snapshot(check.check_id, check.get_health_stream(None), check_states=[{
            'checkStateId': 'check_id',
            'health': 'CRITICAL',
            'message': 'message',
            'name': 'name',
            'topologyElementIdentifier': 'identifier'
        }])

    def test_check_state_min_values(self, health):
        # Min values: fill in as few of the optional fields as possible
        check = HealthCheck()
        check._init_health_api()
        check.health.check_state("check_id", "name", Health.CRITICAL, "identifier")
        health.assert_snapshot(check.check_id, check.get_health_stream(None), check_states=[{
            'checkStateId': 'check_id',
            'health': 'CRITICAL',
            'name': 'name',
            'topologyElementIdentifier': 'identifier'
        }])

    def test_check_state_verify_types(self):
        check = HealthCheck()
        check._init_health_api()
        with pytest.raises(DataError):
            check.health.check_state(1, "name", Health.CRITICAL, "identifier")

        with pytest.raises(DataError):
            check.health.check_state("check_id", 1, Health.CRITICAL, "identifier")

        with pytest.raises(ValueError):
            check.health.check_state("check_id", "name", "bla", "identifier")

        with pytest.raises(DataError):
            check.health.check_state("check_id", "name", Health.CRITICAL, 1)

        with pytest.raises(DataError):
            check.health.check_state("check_id", "name", Health.CRITICAL, "identifier", 1)

    def test_start_snapshot(self, health):
        check = HealthCheck()
        check._init_health_api()
        check.health.start_snapshot()
        health.assert_snapshot(check.check_id,
                               check.get_health_stream(None),
                               start_snapshot={'expiry_interval_s': 60, 'repeat_interval_s': 15},
                               stop_snapshot=None)

    def test_start_snapshot_main_stream(self, health):
        check = HealthCheckMainStream()
        check._init_health_api()
        check.health.start_snapshot()
        health.assert_snapshot(check.check_id,
                               check.get_health_stream(None),
                               start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
                               stop_snapshot=None)

    def test_stop_snapshot(self, health):
        check = HealthCheck()
        check._init_health_api()
        check.health.stop_snapshot()
        health.assert_snapshot(check.check_id,
                               check.get_health_stream(None),
                               start_snapshot=None,
                               stop_snapshot={})

    def test_run_initializes_health_api(self, health):
        check = HealthCheck()
        check.run()
        assert check.health is not None

    def test_run_not_initializes_health_api(self, health):
        check = HealthCheck(stream=None)
        check.run()
        assert check.health is None

    def test_explicit_collection_interval(self, health):
        check = HealthCheck(instance={'collection_interval': 30})
        check._init_health_api()
        check.health.start_snapshot()
        health.assert_snapshot(check.check_id,
                               check.get_health_stream(None),
                               start_snapshot={'expiry_interval_s': 120, 'repeat_interval_s': 30},
                               stop_snapshot=None)


class TestDataDogPersistentCache:

    def test_write_and_read(self):
        check = TopologyCheck()
        check.write_persistent_cache('foo', 'bar')

        assert datadog_agent.read_persistent_cache(check._persistent_cache_id('foo')) == 'bar'
        assert check.read_persistent_cache('foo') == 'bar'

    def test_write_empty_value(self):
        check = TopologyCheck()
        check.write_persistent_cache('foo', '')

        assert datadog_agent.read_persistent_cache(check._persistent_cache_id('foo')) == ''
        assert check.read_persistent_cache('foo') == ''


class SampleStatefulCheck(StatefulAgentCheck):
    """
    This test class is uses dictionaries for instance and state.
    """
    INSTANCE_TYPE = "stateful_check"

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheck, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state["key3"] = "ghi"
        return state, None

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, instance.get("url", ""))


@pytest.fixture
def sample_stateful_check(state, aggregator):
    check = SampleStatefulCheck('test01', {}, {}, instances=[TEST_INSTANCE])
    yield check
    state.reset()
    aggregator.reset()


class InstanceInfo(Model):
    url = URLType(required=True)
    instance_tags = ListType(StringType, default=[])


class State(Model):
    offset = IntType(default=0)


class SampleStatefulCheckWithSchema(StatefulAgentCheck):
    """
    This class uses instance schema and state schema.
    """
    INSTANCE_TYPE = "stateful_check"
    INSTANCE_SCHEMA = InstanceInfo

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SampleStatefulCheckWithSchema, self).__init__(name, init_config, agentConfig, instances)

    def stateful_check(self, instance, state):
        state = State(state)
        state.validate()
        state.offset += 10
        return state, None

    def get_instance_key(self, instance):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance.url))


@pytest.fixture
def sample_stateful_check_with_schema(state, aggregator):
    check = SampleStatefulCheckWithSchema('test02', {}, {}, instances=[TEST_INSTANCE])
    yield check
    state.reset()
    aggregator.reset()


class TestStatefulCheck:

    def test_instance_key_generation(self):
        test_instance = {
            'url': 'http://example.org/api?query_string=123&another=456'
        }
        check = SampleStatefulCheck('test01', {}, {}, [test_instance])
        check.setup()
        assert check.state._get_state_key('test_key') == \
               "stateful_check_httpexampleorgapiquery_string123another456_test_key"

    def test_stateful_check(self, sample_stateful_check, state, aggregator):
        sample_stateful_check.run()

        key = get_test_state_key(sample_stateful_check)
        expected_state = {
            "key3": "ghi"
        }
        assert sample_stateful_check.get_state() == expected_state
        assert state.get_state(sample_stateful_check,
                               sample_stateful_check.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheckV2.OK)

    def test_stateful_check_state_exists(self, sample_stateful_check, state, aggregator):
        """
        State is dictionary in SampleStatefulCheck, so we don't have restrictions to modify state structure.
        """
        # setup existing state
        key = get_test_state_key(sample_stateful_check)
        existing_state = '{"key1": "abc", "key2": "def"}'
        state.set_state(sample_stateful_check,
                        sample_stateful_check.check_id,
                        key,
                        existing_state)

        # run check to create new state
        sample_stateful_check.run()
        expected_state = {
            "key1": "abc",
            "key2": "def",
            "key3": "ghi"
        }
        assert sample_stateful_check.get_state() == expected_state
        assert state.get_state(sample_stateful_check,
                               sample_stateful_check.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check.name, count=1, status=AgentCheckV2.OK)

    def test_stateful_check_with_schema(self, sample_stateful_check_with_schema, state, aggregator):
        sample_stateful_check_with_schema.run()
        key = get_test_state_key(sample_stateful_check_with_schema)
        expected_state = {"offset": 10}
        assert sample_stateful_check_with_schema.get_state() == expected_state
        assert state.get_state(sample_stateful_check_with_schema,
                               sample_stateful_check_with_schema.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.OK)

    def test_stateful_check_with_schema_existing_state(self, sample_stateful_check_with_schema, state, aggregator):
        # setup existing state
        key = get_test_state_key(sample_stateful_check_with_schema)
        existing_state = '{"offset": 20}'
        state.set_state(sample_stateful_check_with_schema,
                        sample_stateful_check_with_schema.check_id,
                        key,
                        existing_state)

        # run the check to alter state
        sample_stateful_check_with_schema.run()
        expected_state = {"offset": 30}
        assert sample_stateful_check_with_schema.get_state() == expected_state
        assert state.get_state(sample_stateful_check_with_schema,
                               sample_stateful_check_with_schema.check_id,
                               key) == json.dumps(expected_state)
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.OK)

    def test_stateful_check_with_invalid_schema(self, sample_stateful_check_with_schema, state, aggregator):
        # setup invalid existing state
        key = get_test_state_key(sample_stateful_check_with_schema)
        existing_state = '{"key_that_is_not_in_schema": "some_value"}'
        state.set_state(sample_stateful_check_with_schema,
                        sample_stateful_check_with_schema.check_id,
                        key,
                        existing_state)

        # run the check that should be critical
        sample_stateful_check_with_schema.run()
        aggregator.assert_service_check(sample_stateful_check_with_schema.name, count=1, status=AgentCheckV2.CRITICAL)
        service_check = aggregator.service_checks(sample_stateful_check_with_schema.name)
        # error should Schema validation error
        assert service_check[0].message == '{"key_that_is_not_in_schema": "Rogue field"}'


class NormalCheck(AgentCheckV2):
    def __init__(self, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(NormalCheck, self).\
            __init__("test", {}, instances)

    def check(self, instance):
        print 'NormalCheck Run'

        return


class TransactionalCheck(TransactionalAgentCheck):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(TransactionalCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "transactional")

    def transactional_check(self, instance, state):
        print 'TransactionalCheck Run'
        return state, None


class StatefulCheck(StatefulAgentCheck):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(StatefulCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "stateful")

    def stateful_check(self, instance, state):
        print 'StatefulCheck Run'

        state['updated'] = True

        return state, None


class TransactionalStateCheck(TransactionalAgentCheck):
    def __init__(self, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(TransactionalStateCheck, self). \
            __init__("test", {}, instances)

    def get_instance_key(self, instance):
        return StackPackInstance("test", "transactional-state")

    def transactional_check(self, instance, state):
        print 'TransactionalStateCheck Run'

        state['transactional'] = True

        self.set_state({"state": "set_state"})

        return state, None


def get_test_state_key(check, key=None):
    if key is None:
        key = check.PERSISTENT_CACHE_KEY

    return generate_state_key(check._get_instance_key().to_string(), key)


class TestAgentChecksV2:

    def test_normal_check(self):
        check = NormalCheck()
        check.run()

    def test_transactional_check(self, transaction):
        check = TransactionalCheck()
        assert check.run() is ""

        transaction.assert_transaction(check.check_id)

    def test_stateful_check(self, state):
        check = StatefulCheck()
        check.run()

        expected_state = {
            "updated": True
        }

        key = get_test_state_key(check)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_state)

    def test_transactional_state_check(self, transaction, state):
        check = TransactionalStateCheck()
        assert check.run() is ""

        transaction.assert_transaction(check.check_id)

        expected_transactional_state = {
            "transactional": True
        }

        key = get_test_state_key(check, check.TRANSACTIONAL_PERSISTENT_CACHE_KEY)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_transactional_state)

        expected_state = {"state": "set_state"}

        key = get_test_state_key(check)
        assert state.get_state(check, check.check_id, key) == json.dumps(expected_state)
