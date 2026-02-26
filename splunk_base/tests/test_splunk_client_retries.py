import pytest
from stackstate_checks.splunk.client import SplunkClient, FinalizeException

from common import FakeInstanceConfig
from http.client import HTTPMessage
from unittest.mock import ANY, Mock, patch, call, PropertyMock
import requests


# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


class mocked_saved_search:
    """
    A Mocked Saved Search Object
    """
    def __init__(self):
        self.name = "components"
        self.request_timeout_seconds = 10
        self.app = "-"


def test_successful_retry_after_two_500s(mocker):
    mock_sleep = mocker.patch("time.sleep")
    # Mocking connection pool to test the configured retry of the requests library.
    getconn_mock = mocker.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")
    # Newer urllib3 versions inspect Retry-After headers; avoid interacting with mocked headers.
    mocker.patch("urllib3.util.retry.Retry.get_retry_after", return_value=None)

    # Avoid reading response content in requests, which would try to iterate our mock raw stream
    mocker.patch.object(requests.models.Response, "content", new_callable=PropertyMock, return_value=b"")

    helper = SplunkClient(FakeInstanceConfig())

    getconn_mock.return_value.getresponse.side_effect = [
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=200, msg=HTTPMessage(), headers={}),
    ]

    helper.finalize_sid("admin_comp1", mocked_saved_search())
    # We expect 3 POST attempts: initial + 2 retries
    assert getconn_mock.return_value.request.call_count == 3


def test_produce_failure_after_retries(mocker):
    mock_sleep = mocker.patch("time.sleep")
    # Mocking connection pool to test the configured retry of the requests library.
    getconn_mock = mocker.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")
    mocker.patch("urllib3.util.retry.Retry.get_retry_after", return_value=None)

    mocker.patch.object(requests.models.Response, "content", new_callable=PropertyMock, return_value=b"")

    helper = SplunkClient(FakeInstanceConfig())

    getconn_mock.return_value.getresponse.side_effect = [
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=500, msg=HTTPMessage(), headers={}),
        Mock(status=500, msg=HTTPMessage(), headers={}),
    ]

    with pytest.raises(FinalizeException):
        helper.finalize_sid("admin_comp1", mocked_saved_search())
    # We expect 5 POST attempts before giving up
    assert getconn_mock.return_value.request.call_count == 5
