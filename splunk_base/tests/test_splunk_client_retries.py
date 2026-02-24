import pytest
from stackstate_checks.splunk.client import SplunkClient, FinalizeException

from common import FakeInstanceConfig
from http.client import HTTPMessage
from unittest.mock import ANY, Mock, patch, call


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

    helper = SplunkClient(FakeInstanceConfig())

    getconn_mock.return_value.getresponse.side_effect = [
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=200, msg=HTTPMessage()),
    ]

    helper.finalize_sid("admin_comp1", mocked_saved_search())

    assert mock_sleep.call_count == 1
    assert getconn_mock.return_value.request.mock_calls == [
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
    ]


def test_produce_failure_after_retries(mocker):
    mock_sleep = mocker.patch("time.sleep")
    # Mocking connection pool to test the configured retry of the requests library.
    getconn_mock = mocker.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")

    helper = SplunkClient(FakeInstanceConfig())

    getconn_mock.return_value.getresponse.side_effect = [
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=500, msg=HTTPMessage()),
        Mock(status=500, msg=HTTPMessage()),
    ]

    with pytest.raises(FinalizeException):
        helper.finalize_sid("admin_comp1", mocked_saved_search())

    assert mock_sleep.call_count == 3
    assert getconn_mock.return_value.request.mock_calls == [
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
        call("POST", '/services/search/jobs/admin_comp1/control?output_mode=json', body='action=finalize', headers=ANY),
    ]
