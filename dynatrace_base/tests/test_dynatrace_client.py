# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


def test_endpoint_generation(dynatrace_client):
    """
    Check if the URL sanitization is correct.
    """
    urls = ["https://custom.domain.com/e/abc123", "https://custom.domain.com/e/abc123/"]
    paths = ["api/v1/entity/infrastructure/processes", "/api/v1/entity/infrastructure/processes"]
    expected_url = "https://custom.domain.com/e/abc123/api/v1/entity/infrastructure/processes"
    for url in urls:
        for path in paths:
            assert dynatrace_client.get_endpoint(url, path) == expected_url


def test_raising_exception_on_not_200_status(dynatrace_client, requests_mock, test_instance):
    """
    Check if client raised exception on non 200 status.
    """
    endpoint = dynatrace_client.get_endpoint(test_instance.get('url'), '/api/v1/events')
    requests_mock.get(endpoint, text='{"response": "123"}', status_code=400)
    with pytest.raises(Exception):
        dynatrace_client.get_dynatrace_json_response(endpoint)


def test_status_200(dynatrace_client, requests_mock, test_instance):
    """
    Basic client test.
    """
    endpoint = dynatrace_client.get_endpoint(test_instance.get('url'), 'api/v1/events/')
    requests_mock.get(endpoint, text='{"events": [{"eventId": "123"}]}', status_code=200)
    response = dynatrace_client.get_dynatrace_json_response(endpoint)
    assert response["events"][0]['eventId'] == '123'


def test_entity_404_handling_single_type(dynatrace_client, requests_mock, test_instance, caplog):
    """
    Test that 404 errors for entities are logged at INFO level with counting.
    """
    import logging
    caplog.set_level(logging.INFO)

    # Create multiple 404 endpoints for the same entity type
    base_url = test_instance.get('url')
    endpoints = [
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-123'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-456'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-789'),
    ]

    # Mock all endpoints to return 404
    for endpoint in endpoints:
        requests_mock.get(endpoint, text='{"error": {"message": "Entity not found"}}', status_code=404)

    # Make requests to all endpoints
    for endpoint in endpoints:
        with pytest.raises(Exception):  # Client should still raise exception
            dynatrace_client.get_dynatrace_json_response(endpoint)

    # Check that only one INFO log message was created for this entity type
    info_logs = [record for record in caplog.records if record.levelname == 'INFO']
    assert len(info_logs) == 1
    assert 'CLOUD_APPLICATION_NAMESPACE' in info_logs[0].message
    assert 'first occurrence' in info_logs[0].message
    assert 'Count: 1' in info_logs[0].message

    # Check that the count is tracked correctly
    summary = dynatrace_client.get_entity_404_summary()
    assert summary['CLOUD_APPLICATION_NAMESPACE'] == 3


def test_entity_404_handling_multiple_types(dynatrace_client, requests_mock, test_instance, caplog):
    """
    Test that 404 errors for different entity types are logged separately.
    """
    import logging
    caplog.set_level(logging.INFO)

    base_url = test_instance.get('url')
    endpoints = [
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-123'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/PROCESS_GROUP_INSTANCE-456'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/HOST-789'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-999'),
    ]

    # Mock all endpoints to return 404
    for endpoint in endpoints:
        requests_mock.get(endpoint, text='{"error": {"message": "Entity not found"}}', status_code=404)

    # Make requests to all endpoints
    for endpoint in endpoints:
        with pytest.raises(Exception):
            dynatrace_client.get_dynatrace_json_response(endpoint)

    # Check that we have INFO logs for each entity type (but not duplicates)
    info_logs = [record for record in caplog.records if record.levelname == 'INFO']
    assert len(info_logs) == 3  # One for each unique entity type

    entity_types_logged = []
    for log in info_logs:
        if 'CLOUD_APPLICATION_NAMESPACE' in log.message:
            entity_types_logged.append('CLOUD_APPLICATION_NAMESPACE')
        elif 'PROCESS_GROUP_INSTANCE' in log.message:
            entity_types_logged.append('PROCESS_GROUP_INSTANCE')
        elif 'HOST' in log.message:
            entity_types_logged.append('HOST')

    assert set(entity_types_logged) == {'CLOUD_APPLICATION_NAMESPACE', 'PROCESS_GROUP_INSTANCE', 'HOST'}

    # Check counts
    summary = dynatrace_client.get_entity_404_summary()
    assert summary['CLOUD_APPLICATION_NAMESPACE'] == 2
    assert summary['PROCESS_GROUP_INSTANCE'] == 1
    assert summary['HOST'] == 1


def test_entity_404_summary_logging(dynatrace_client, requests_mock, test_instance, caplog):
    """
    Test that the 404 summary is logged correctly.
    """
    import logging
    caplog.set_level(logging.INFO)

    base_url = test_instance.get('url')
    endpoints = [
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-1'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/CLOUD_APPLICATION_NAMESPACE-2'),
        dynatrace_client.get_endpoint(base_url, '/api/v2/entities/HOST-1'),
    ]

    # Mock endpoints to return 404
    for endpoint in endpoints:
        requests_mock.get(endpoint, text='{"error": {"message": "Entity not found"}}', status_code=404)

    # Generate some 404s
    for endpoint in endpoints:
        with pytest.raises(Exception):
            dynatrace_client.get_dynatrace_json_response(endpoint)

    # Clear previous logs and call summary
    caplog.clear()
    dynatrace_client.log_entity_404_summary()

    # Check summary log
    info_logs = [record for record in caplog.records if record.levelname == 'INFO']
    assert len(info_logs) == 1
    summary_log = info_logs[0].message

    assert 'Summary: 3 total 404 errors across 2 entity types:' in summary_log
    assert 'CLOUD_APPLICATION_NAMESPACE: 2 occurrences' in summary_log
    assert 'HOST: 1 occurrences' in summary_log


def test_entity_404_no_summary_when_no_errors(dynatrace_client, caplog):
    """
    Test that no summary is logged when there are no 404 errors.
    """
    import logging
    caplog.set_level(logging.INFO)

    # Call summary without any 404s
    dynatrace_client.log_entity_404_summary()

    # Should have no log messages
    info_logs = [record for record in caplog.records if record.levelname == 'INFO']
    assert len(info_logs) == 0
