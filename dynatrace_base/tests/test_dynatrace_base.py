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

    """
    endpoint = dynatrace_client.get_endpoint(test_instance.get('url'), 'api/v1/events/')
    requests_mock.get(endpoint, text='{"events": [{"eventId": "123"}]}', status_code=200)
    response = dynatrace_client.get_dynatrace_json_response(endpoint)
    assert response["events"][0]['eventId'] == '123'
