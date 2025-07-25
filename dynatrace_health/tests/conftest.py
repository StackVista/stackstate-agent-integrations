# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import re

import pytest

from stackstate_checks.dynatrace_health import DynatraceHealthCheck


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "url": "https://ton48129.live.dynatrace.com",
        "token": "some_token",
        'collection_interval': 15
    }


@pytest.fixture(scope='class')
def test_instance():
    return {
        "url": "https://instance.live.dynatrace.com",
        "token": "some_token",
        "events_process_limit": 10,
        "events_boostrap_days": 5,
        "timeout": 20,
        'collection_interval': 15
    }


@pytest.fixture
def dynatrace_check(test_instance, health, aggregator, telemetry, topology):
    check = DynatraceHealthCheck('dynatrace', {}, instances=[test_instance])
    yield check
    aggregator.reset()
    telemetry.reset()
    topology.reset()
    health.reset()
    check.commit_state(None)


def set_http_responses(requests_mock, availability_event='{}', error_event='{}', performance_event='{}',
                       resource_contention_event='{}', custom_deployment_event='{}', custom_annotation_event='{}',
                       custom_info_event='{}', marked_for_termination_event='{}', custom_alert_event='{}',
                       custom_configuration_event='{}'):
    """
    Mock the HTTP responses for event type details.
    `kwargs` should be a dictionary where keys are event type names (e.g., 'AVAILABILITY_EVENT')
    and values are the JSON string responses.
    """
    availability_event_url_pattern = re.compile(r'/api/v2/eventTypes/AVAILABILITY_EVENT$')
    requests_mock.get(availability_event_url_pattern, text=availability_event, status_code=200)

    error_event_url_pattern = re.compile(r'/api/v2/eventTypes/ERROR_EVENT$')
    requests_mock.get(error_event_url_pattern, text=error_event, status_code=200)

    performance_event_url_pattern = re.compile(r'/api/v2/eventTypes/PERFORMANCE_EVENT$')
    requests_mock.get(performance_event_url_pattern, text=performance_event, status_code=200)

    resource_contention_event_url_pattern = re.compile(r'/api/v2/eventTypes/RESOURCE_CONTENTION$')
    requests_mock.get(resource_contention_event_url_pattern, text=resource_contention_event, status_code=200)

    custom_deployment_event_url_pattern = re.compile(r'/api/v2/eventTypes/CUSTOM_DEPLOYMENT$')
    requests_mock.get(custom_deployment_event_url_pattern, text=custom_deployment_event, status_code=200)

    custom_annotation_event_url_pattern = re.compile(r'/api/v2/eventTypes/CUSTOM_ANNOTATION$')
    requests_mock.get(custom_annotation_event_url_pattern, text=custom_annotation_event, status_code=200)

    custom_info_event_url_pattern = re.compile(r'/api/v2/eventTypes/CUSTOM_INFO$')
    requests_mock.get(custom_info_event_url_pattern, text=custom_info_event, status_code=200)

    marked_for_termination_event_url_pattern = re.compile(r'/api/v2/eventTypes/MARKED_FOR_TERMINATION$')
    requests_mock.get(marked_for_termination_event_url_pattern, text=marked_for_termination_event, status_code=200)

    custom_alert_event_url_pattern = re.compile(r'/api/v2/eventTypes/CUSTOM_ALERT$')
    requests_mock.get(custom_alert_event_url_pattern, text=custom_alert_event, status_code=200)

    custom_configuration_event_url_pattern = re.compile(r'/api/v2/eventTypes/CUSTOM_CONFIGURATION$')
    requests_mock.get(custom_configuration_event_url_pattern, text=custom_configuration_event, status_code=200)
