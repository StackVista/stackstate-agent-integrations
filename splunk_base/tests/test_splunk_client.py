import pytest

# stdlib
import unittest

# 3p
import mock
import json
from requests.exceptions import HTTPError, ConnectionError, Timeout
from requests import Response

import datetime

# project
from stackstate_checks.splunk.client import SplunkClient, FinalizeException, TokenExpiredException
from stackstate_checks.splunk.config import AuthType, SplunkPersistentState

from common import FakeInstanceConfig, FakeTokenInstanceConfig
from stackstate_checks.splunk.config.splunk_instance_config_models import SavedSearchErrorBehavior

# Mark the entire module as tests of type `unit`
pytestmark = pytest.mark.unit


class FakeResponse(object):
    def __init__(self, text, status_code=200, headers={}):
        self.status_code = status_code
        self.payload = text
        self.headers = headers
        self.content = text

    def json(self):
        return json.loads(self.payload)

    def raise_for_status(self):
        return


class mocked_saved_search:
    """
    A Mocked Saved Search Object
    """
    def __init__(self):
        self.name = "components"
        self.request_timeout_seconds = 10
        self.app = "-"


class MockResponse(Response):
    """
    A Mocked Response for request_session post method
    """
    def __init__(self, json_data):
        Response.__init__(self)
        self.json_data = json_data
        self.status_code = json_data["status_code"]
        self.reason = json_data["reason"]
        self.url = json_data["url"]

    def json(self):
        return self.json_data


def mocked_token_create_response():
    return json.dumps({
        "entry": [
            {
                "name": "tokens",
                "id": "https://shc-api-p1.splunk.prd.ss.aws.insim.biz/services/authorization/tokens/tokens",
                "updated": "1970-01-01T01:00:00+01:00",
                "links": {
                    "alternate": "/services/authorization/tokens/tokens",
                    "list": "/services/authorization/tokens/tokens",
                    "edit": "/services/authorization/tokens/tokens",
                    "remove": "/services/authorization/tokens/tokens"
                },
                "author": "system",
                "content": {
                    "id": "29f344ad6f98a2370e18249a58f4acea1e6775982f102b34bec5f9ee5f9af76c",
                    "token": "eyJraWQiOiJzcGx1bmsuc2VjcmV0IiwiYWxnIjoiSFM1MTIiLCJ2ZXIiJ2MSIsInR0eXAiOiJzdGF0MifQ.eyJpc3"
                             "MiOiJhcGktbnBHp6YXBwMDcyBmcm9tIHNoX2NsX3AxXzAzIiwic3ViIjoiYXBpLW5wYC89uY6emFDA3OTciLCJhdW"
                             "QiOiJOTl9OTF9CYW5rX01DIiwiaWRwIjoic3BsdW5rIiwianRpIjoiMjlmMzQ0YWQ2Zjk4YTIzNzBlMTgyNDlhNTh"
                             "mNGFjZWExZTY3NzU5ODJmMTAyYjM0YmVjNWY5ZWU1ZjlhZjc2YyIsImlhdCI6MTU4MDEzOTUzNCwiZXhwIjoxNTg3"
                             "OTExOTM0LCJuYnIiOjE1ODAxMzk1MzR9.-5aNGmPmmQeSO8VqxX3CSzARPBiXhDzofrFnBDYdFxnHqHC5e2WQ1iii"
                             "DrYJv1P3buvGytA5bG6TYXO9Ow"
                }
            }
        ]
    })


class TestSplunkClient(unittest.TestCase):
    """
    Test the Splunk Client class
    """

    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse("""{ "sessionKey": "MySessionKeyForThisSession" }""", headers={}))
    def test_auth_session_fallback(self, mocked_do_post):
        """
        Test request authentication on fallback Authentication header
        retrieve auth session key,
        set it to the requests session,
        and see whether the outgoing request contains the expected HTTP header
        The expected HTTP header is Authentication when Set-Cookie is not present
        """
        instance = FakeInstanceConfig()
        helper = SplunkClient(instance)
        helper.auth_session({})

        mocked_do_post.assert_called_with("/services/auth/login?output_mode=json",
                                          "username=username&password=password&cookie=1",
                                          10)
        mocked_do_post.assert_called_once()

        expected_header = helper.requests_session.headers.get("Authentication")
        self.assertEqual(expected_header, "Splunk MySessionKeyForThisSession")

    def test_dispatch_with_on_saved_search_error_ignore(self):
        """
        Test dispatch method to get value None in case of flag on_saved_search_error='ignore'
        """

        path = '/servicesNS/%s/%s/saved/searches/%s/dispatch' % ("admin", "search", "component")
        helper = SplunkClient(FakeInstanceConfig())

        # Mock the post response of request_session
        helper.requests_session.post = mock.MagicMock()
        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Not Found", "status_code": 404, "url": path})

        res = helper.dispatch(mocked_saved_search(),
                              helper.instance_config.on_saved_search_error, None)

        self.assertEqual(res, None)

    def test_dispatch_with_on_saved_search_error_abort(self):
        """
        Test dispatch method to get value None in case of flag on_saved_search_error='abort'
        """

        path = '/servicesNS/%s/%s/saved/searches/%s/dispatch' % ("admin", "search", "component")
        helper = SplunkClient(FakeInstanceConfig())
        helper.instance_config.on_saved_search_error = SavedSearchErrorBehavior.abort

        # Mock the post response of request_session
        helper.requests_session.post = mock.MagicMock()
        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Not Found", "status_code": 404, "url": path})

        self.assertRaises(HTTPError, helper.dispatch, mocked_saved_search(),
                          helper.instance_config.on_saved_search_error, None)

    def test_finalize_sid(self):
        """
        Test finalize_sid method to successfully pass
        """
        url = FakeInstanceConfig().base_url
        helper = SplunkClient(FakeInstanceConfig())
        helper.requests_session.post = mock.MagicMock()
        helper.requests_session.post.return_value = FakeResponse(status_code=200, text="done")
        # return None when response is 200
        self.assertEqual(helper.finalize_sid("admin_comp1", mocked_saved_search()), None)

        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Unknown Sid", "status_code": 404, "url": url})
        # return None when sid not found because we want to continue
        self.assertEqual(helper.finalize_sid("admin_comp1", mocked_saved_search()), None)

        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Internal Server error", "status_code": 500, "url": url})
        # return finalize exception when api returns 500
        self.assertRaises(FinalizeException, helper.finalize_sid, "admin_comp1", mocked_saved_search())

        helper.requests_session.post = mock.MagicMock(side_effect=Timeout())
        # return finalize exception when timeout occurs
        self.assertRaises(FinalizeException, helper.finalize_sid, "admin_comp1", mocked_saved_search())

        helper.requests_session.post = mock.MagicMock(side_effect=ConnectionError())
        # return finalize exception when connection error occurs
        self.assertRaises(FinalizeException, helper.finalize_sid, "admin_comp1", mocked_saved_search())

    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_create_auth_token(self, mocked_response):
        """
        Test token creation method for initial token
        """
        new_token = json.loads(mocked_token_create_response()).get('entry')[0].get('content').get('token')

        helper = SplunkClient(FakeTokenInstanceConfig())
        generated_token = helper._create_auth_token("test")
        name = helper.instance_config.auth_config.name
        audience = helper.instance_config.auth_config.audience
        expiry_days = helper.instance_config.auth_config.token_expiration_days
        payload = {'name': name, 'audience': audience, 'expires_on': "+{}d".format(str(expiry_days))}
        mocked_response.assert_called_with("/services/authorization/tokens?output_mode=json", payload, 10)
        mocked_response.assert_called_once()

        # New token from response and generated token should be same
        self.assertEqual(generated_token, new_token)
        # Initial token and new token should differ
        self.assertNotEqual("test", new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session(self, mocked_decode_token):
        """
        Test token_auth_session when memory token is valid and doesn't need renewal
        """
        # load a token in memory for validation
        status = SplunkPersistentState({})
        status.set_auth_token('memorytokenpresent')

        helper = SplunkClient(FakeTokenInstanceConfig())
        # update headers with memory token
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper.jwt_adapter._current_time = mock.MagicMock()
        helper.jwt_adapter._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        helper.auth_session(status)

        # Header should be still with the memory token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format("memorytokenpresent"))

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_token_auth_session_need_renewal_initial_token(self, mocked_decode_token, moccked_post):
        """
        Test token_auth_session when initial token need to be refreshed
        """
        new_token = json.loads(mocked_token_create_response()).get('entry')[0].get('content').get('token')

        status = SplunkPersistentState({})
        helper = SplunkClient(FakeTokenInstanceConfig())
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper.jwt_adapter._current_time = mock.MagicMock()
        helper.jwt_adapter._current_time.return_value = datetime.datetime(2020, 6, 5, 15, 44, 51)
        helper._token_auth_session(status)

        # Header should be updated with the new token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format(new_token))
        # persistence data will have new updated token
        self.assertEqual(status.get_auth_token(), new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 0, "iat": 1584021915, "aud": "stackstate"})
    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_token_auth_session_use_initial_token_no_expiry(self, mocked_decode_token, moccked_post):
        """
        Test token_auth_session when initial token has unlimited expiration
        """

        status = SplunkPersistentState({})
        helper = SplunkClient(FakeTokenInstanceConfig())
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper.jwt_adapter._current_time = mock.MagicMock()
        helper.jwt_adapter._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        helper._token_auth_session(status)

        # Header should be updated with the new token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format(FakeTokenInstanceConfig().auth_config.initial_token))
        # initial token should not be stored in state
        self.assertEqual(status.get_auth_token(), None)

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_token_auth_session_need_renewal_memory_token(self, mocked_decode_token, moccked_post):
        """
        Test token_auth_session when memory token about to expire and need to be refreshed
        """
        new_token = json.loads(mocked_token_create_response()).get('entry')[0].get('content').get('token')

        status = SplunkPersistentState({})
        # load a token in memory for validation
        status.set_auth_token('memorytokenpresent')
        helper = SplunkClient(FakeTokenInstanceConfig())
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper.jwt_adapter._current_time = mock.MagicMock()
        helper.jwt_adapter._current_time.return_value = datetime.datetime(2020, 6, 5, 15, 44, 51)
        helper.auth_session(status)

        # Header should be updated with the new token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format(new_token))
        # persistence data will have new token as well
        self.assertEqual(status.get_auth_token(), new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session_invalid_initial_token(self, mocked_decode_token):
        """
        Test token_auth_session to throw TokenExpiredException when initial token is expired
        """
        status = SplunkPersistentState({})
        helper = SplunkClient(FakeTokenInstanceConfig())
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 6, 16, 15, 44, 51)
        check = False
        try:
            helper.auth_session(status)
        except TokenExpiredException:
            check = True
        msg = "Current in use authentication token is expired. Please provide a valid token in the YAML " \
              "and restart the Agent"
        self.assertTrue(check, msg)

    @mock.patch('stackstate_checks.splunk.client.splunk_jwt_auth.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session_invalid_memory_token(self, mocked_decode_token):
        """
        Test token_auth_session to throw TokenExpiredException when memory token is expired
        """
        status = SplunkPersistentState({})
        # load a token in memory for validation
        status.set_auth_token('memorytokenpresent')
        helper = SplunkClient(FakeTokenInstanceConfig())
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 6, 16, 15, 44, 51)
        check = False
        try:
            helper.auth_session(status)
        except TokenExpiredException:
            check = True
        msg = "Current in use authentication token is expired. Please provide a valid token in the YAML " \
              "and restart the Agent"
        self.assertTrue(check, msg)

    def test_client_get_saved_search_path(self):
        """
        Test token_auth_session to throw TokenExpiredException when memory token is expired
        """
        status = SplunkPersistentState({})
        # load a token in memory for validation
        status.set_auth_token('memorytokenpresent')
        client = SplunkClient(FakeTokenInstanceConfig())
        client.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        client._current_time = mock.MagicMock()
        client._current_time.return_value = datetime.datetime(2020, 6, 16, 15, 44, 51)

        search_path = client._get_saved_search_path("nobody", "test_app")
        self.assertEqual(search_path, "/servicesNS/nobody/test_app/saved/searches/?output_mode=json&count=-1")
