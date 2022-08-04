# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
import os

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import TokenExpiredException
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance
from stackstate_checks.splunk_event.splunk_event import SplunkEvent

CHECK_NAME = "splunk"


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

    def _build_instance(self, instance, current_time, metric_instance_config, saved_search):
        return MockedInstance(instance, self.init_config)


def test_splunk_error_response(instance, saved_searches_error, aggregator):
    check = MockedSplunkEvent(CHECK_NAME, {}, {}, [instance])
    check.run()
    print(aggregator.service_checks(CHECK_NAME)[0].message)
    # assert 1 == 2
