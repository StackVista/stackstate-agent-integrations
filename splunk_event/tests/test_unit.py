# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os
import unittest

import pytest

from stackstate_checks.base import AgentCheck
from stackstate_checks.base.errors import CheckException
from stackstate_checks.base.stubs import aggregator
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance
from stackstate_checks.splunk_event.splunk_event import SplunkEvent

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')


def load_fixture(fixture_file):
    with open(os.path.join(FIXTURE_DIR, fixture_file)) as f:
        return json.loads(f.read())


class MockSplunkClient(object):
    def __init__(self):
        self._dispatch_parameters = None
        self.invalid_token = False

    def auth_session(self, committable_state):
        if self.invalid_token:
            raise TokenExpiredException("Current in use authentication token is expired. Please provide a valid "
                                        "token in the YAML and restart the Agent")
        return

    def saved_searches(self):
        return []

    def saved_search_results(self, search_id, saved_search):
        if search_id == "exception":
            raise CheckException("maximum retries reached for saved search " + str(search_id))
        # sid is set to saved search name
        return [load_fixture("%s.json" % search_id)]

    def dispatch(self, saved_search, splunk_app, ignore_saved_search_errors, parameters):
        if saved_search.name == "dispatch_exception":
            raise Exception("BOOM")
        self._dispatch_parameters = parameters
        return saved_search.name

    def finalize_sid(self, search_id, saved_search):
        return


class MockedInstance(SplunkTelemetryInstance):
    def __init__(self, *args, **kwargs):
        super(MockedInstance, self).__init__(*args, **kwargs)

    def _build_splunk_client(self):
        return MockSplunkClient()


class MockedSplunkEvent(SplunkEvent):
    def __init__(self, *args, **kwargs):
        super(MockedSplunkEvent, self).__init__(*args, **kwargs)

    def _build_instance(self, current_time, instance, metric_instance_config, _create_saved_search):
        return MockedInstance(current_time, instance, metric_instance_config, _create_saved_search)


class TestSplunk(unittest.TestCase):
    CHECK_NAME = "splunk_event"
    instance = {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [],
        'tags': []
    }

    def Setup(self):
        """
        Initialize and patch the check, i.e.
        """
        self.check = MockedSplunkEvent(self.CHECK_NAME, {}, {}, [self.instance])
        aggregator.reset()
        self.check.set_state({})


class TestSplunkErrorResponse(TestSplunk):
    """Splunk event check should handle a FATAL message response."""
    instance = {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [{
            "name": "error",
            "parameters": {}
        }],
        'tags': []
    }

    def test_checks(self):
        check = MockedSplunkEvent(self.CHECK_NAME, {}, {}, [self.instance])
        self.assertEqual(check.run(), "", "Check run result shouldn't return error message.")
        service_checks = aggregator.service_checks(SplunkEvent.SERVICE_CHECK_NAME)
        self.assertEqual(AgentCheck.CRITICAL, service_checks[0].status, "Handle a FATAL message response.")


class TestSplunkEmptyEvents(TestSplunk):
    """Splunk event check should process empty response correctly."""
    instance = {
        'url': 'http://localhost:8089',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [{
            "name": "empty",
            "parameters": {}
        }],
        'tags': []

    }

    def test_checks(self):
        check = MockedSplunkEvent(self.CHECK_NAME, {}, {}, [self.instance])
        self.assertEqual(check.run(), "", "Check run result shouldn't return error message.")
        service_checks = aggregator.service_checks(SplunkEvent.SERVICE_CHECK_NAME)
        self.assertEqual(AgentCheck.OK, service_checks[0].status, "Processing empty response.")
        self.assertEqual([], aggregator.events)


class TestSplunkMinimalEvents(TestSplunk):
    """Splunk event check should process minimal response correctly."""

    instance = {
        'url': 'http://localhost:13001',
        'authentication': {
            'basic_auth': {
                'username': "admin",
                'password': "admin"
            }
        },
        'saved_searches': [{
            "name": "minimal_events",
            "parameters": {}
        }],
        'tags': []
    }

    def test_checks(self):
        check = MockedSplunkEvent(self.CHECK_NAME, {}, {}, [self.instance])
        self.assertEqual(check.run(), "", "Check run result shouldn't return error message.")
        self.assertEqual(2, len(aggregator.events), "There should be two events processed.")
        self.assertEqual(aggregator.events[0], {
            'event_type': None,
            'tags': [],
            'timestamp': 1488974400.0,
            'msg_title': None,
            'msg_text': None,
            'source_type_name': None
        })
        self.assertEqual(aggregator.events[1], {
            'event_type': None,
            'tags': [],
            'timestamp': 1488974400.0,
            'msg_title': None,
            'msg_text': None,
            'source_type_name': None
        })
