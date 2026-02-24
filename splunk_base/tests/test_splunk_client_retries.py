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

# @patch("time.sleep")
# def test_max_retries_exceeded_with_requests_mock(self, mock_sleep):
#     url = "https://api.example.com/broken"
#     session = create_retry_session(retries=2, backoff_factor=1)
#
#     with requests_mock.Mocker() as m:
#         # If you just pass a single dictionary, it returns it infinitely
#         m.get(url, status_code=500)
#
#         # Assert that the RetryError is raised after max attempts
#         with self.assertRaises(requests.exceptions.RetryError):
#             session.get(url)
#
#         # Initial request + 2 retries = 3 total calls
#         self.assertEqual(m.call_count, 3)
#         self.assertEqual(mock_sleep.call_count, 2)
#
# def test_jwt_adapter_msft_client(requests_mock: Mocker):
#     """
#     Test JWT adapter Microsoft AD JWT client
#     """
#     status = SplunkPersistentState({})
#
#     client = SplunkClient(FakeInstanceConfig())
#     client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
#
#     requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
#                        json={"access_token": fake_jwt, "expires_in": 3600},
#                        status_code=200)
#
#     client.auth_session(status)
#     assert client.requests_session.headers['Authorization'] == f"Bearer {fake_jwt}"
#
#
# def test_jwt_adapter_msft_client_partial_config(requests_mock: Mocker):
#     """
#     Test JWT adapter Microsoft AD JWT client
#     """
#     # Create a valid-looking fake JWT for the mock response
#     exp_time = int(time.time()) + 3600
#     header = {"alg": "RS256", "typ": "JWT"}
#     payload = {"exp": exp_time}
#     encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
#     encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
#     fake_signature = base64.urlsafe_b64encode(b'fakesignature').rstrip(b'=').decode()
#     fake_jwt = f"{encoded_header}.{encoded_payload}.{fake_signature}"
#
#     os.environ["CLIENT_ID"] = "test"
#     os.environ["CLIENT_SECRET"] = "test"
#     os.environ["SCOPE"] = "test"
#     os.environ["TENANT_ID"] = "test-tenant-id"
#
#     status = SplunkPersistentState({})
#
#     client = SplunkClient(FakeMinimalTokenMSInstanceConfig())
#     client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
#
#     requests_mock.post("https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token",
#                        json={"access_token": fake_jwt, "expires_in": 3600},
#                        status_code=200)
#
#     client.auth_session(status)
#     assert client.requests_session.headers['Authorization'] == f"Bearer {fake_jwt}"
