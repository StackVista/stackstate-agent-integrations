# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import logging
import json
import os

from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk_metric.splunk_metric import SplunkMetric
from stackstate_checks.splunk.telemetry.splunk_telemetry import SplunkTelemetryInstance
from stackstate_checks.splunk.client import SplunkClient
from stackstate_checks.splunk.saved_search_helper import SavedSearches

log = logging.getLogger('{}.{}'.format(__name__, "metric-check-name"))


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'ci', 'fixtures')


def dispatch_saved_search(*args, **kwargs):
    return args[1].name


def search(*args, **kwargs):
    return []


def auth_session(self, committable_state):
    return "sessionKey1"


def finalize_sid_none(*args, **kwargs):
    return None


def saved_searches(*args, **kwargs):
    return []


def load_fixture(fixture_file):
    with open(os.path.join(FIXTURE_DIR, fixture_file)) as f:
        return json.loads(f.read())


def saved_search_results(self, search_id, saved_search):
    if search_id == "exception":
        raise CheckException("maximum retries reached for saved search " + str(saved_search.name))

    return [load_fixture("%s.json" % saved_search.name)]


def _build_splunk_client(self):
    splunk_client = SplunkClient
    splunk_client.auth_session = auth_session
    splunk_client.finalize_sid = finalize_sid_none
    splunk_client.saved_searches = saved_searches
    splunk_client.saved_search_results = saved_search_results

    return splunk_client(self.instance_config)


# Overwrite func: _build_instance
# Func Location: SplunkMetric(SplunkTelemetryBase)._build_instance
def _build_instance(current_time, instance, metric_instance_config, _create_saved_search):
    # type: (int, any, any, any) -> SplunkTelemetryInstance

    saved_search = SavedSearches
    saved_search._dispatch_saved_search = dispatch_saved_search

    splunk_telemetry_instance = SplunkTelemetryInstance
    splunk_telemetry_instance._build_splunk_client = _build_splunk_client
    splunk_telemetry_instance.saved_search_helper = saved_search

    return splunk_telemetry_instance(current_time, instance, metric_instance_config, _create_saved_search)


def test_splunk_hello_world():
    config = {
        'init_config': {},
        'instances': [
            {
                'url': 'http://localhost:13001',
                'authentication': {
                    'basic_auth': {
                        'username': "admin",
                        'password': "admin"
                    }
                },
                'saved_searches': [{
                    "name": "minimal_metrics",
                    "parameters": {}
                }],
                'tags': []
            }
        ]
    }

    check = SplunkMetric("metric-check-name", config['init_config'], {}, config['instances'])
    check._build_instance = _build_instance

    check.run()

    assert 1 == 1
