# -*- coding: utf-8 -*-

# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import mock
import pytest
from six import PY3

from stackstate_checks.checks import AgentCheck, TopologyInstance, AgentIntegrationInstance
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
            "event_type": "new.event",
            "msg_title": "new test event",
            "aggregation_key": "test.event",
            "msg_text": "test event test event",
            "tags": None
        }
        check.event(event)
        aggregator.assert_event('test event test event')


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
        assert len(check.get_warnings()) == 1

        for i in range(0, 42):
            check.gauge("metric", 0)
        assert len(check.get_warnings()) == 1  # get_warnings resets the array
        assert len(aggregator.metrics("metric")) == 10


class TopologyCheck(AgentCheck):
    def __init__(self, key=None):
        super(TopologyCheck, self).__init__()
        self.key = key or TopologyInstance("mytype", "someurl")

    def get_instance_key(self, instance):
        return self.key


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

    def test_start_snapshot(self, topology):
        check = TopologyCheck()
        topology.submit_start_snapshot(check, check.check_id, check._get_instance_key())
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True)

    def test_stop_snapshot(self, topology):
        check = TopologyCheck()
        topology.submit_stop_snapshot(check, check.check_id, check._get_instance_key())
        topology.assert_snapshot(check.check_id, check.key, stop_snapshot=True)

    def test_none_data_ok(self, topology):
        check = TopologyCheck()
        check.component("my-id", "my-type", None)
        topology.assert_snapshot(check.check_id, check.key, components=[component("my-id", "my-type", {})])

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
expected TopologyInstance or AgentIntegrationInstance"""
        else:
            assert str(e.value) == """Got unexpected <type 'dict'> for argument get_instance_key(), \
expected TopologyInstance or AgentIntegrationInstance"""

    def test_illegal_instance_key_field_type(self):
        check = TopologyCheck()
        check.key = TopologyInstance("mytype", 1)
        with pytest.raises(ValueError) as e:
            assert check.component("my-id", "my-type", None)
        assert str(e.value) == "Instance requires a 'url' field of type 'string'"

    def test_topology_instance(self):
        check = TopologyCheck()
        check.key = TopologyInstance("mytype", "myurl")
        assert check.key.toDict() == {"type": "mytype", "url": "myurl"}

    def test_agent_integration_instance(self):
        check = TopologyCheck()
        check.key = AgentIntegrationInstance()
        assert check.key.toDict() == {"type": "agent", "url": "integrations"}
