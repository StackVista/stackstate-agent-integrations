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


class FakeInstanceConfig(object):
    def __init__(self):
        self.base_url = 'http://testhost:8089'
        self.default_request_timeout_seconds = 10
        self.verify_ssl_certificate = False
        self.ignore_saved_search_errors = True
        self.username = "admin"
        self.audience = "test"
        self.name = "admin"
        self.token_expiration_days = 90
        self.renewal_days = 10
        self.initial_token = "asdfg"
        self.auth_type = AuthType.BasicAuth

    def get_auth_tuple(self):
        return ('username', 'password')


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
        instance.auth_type = AuthType.BasicAuth
        helper = SplunkClient(instance)
        helper.auth_session({})

        mocked_do_post.assert_called_with("/services/auth/login?output_mode=json",
                                          "username=username&password=password&cookie=1",
                                          10)
        mocked_do_post.assert_called_once()

        expected_header = helper.requests_session.headers.get("Authentication")
        self.assertEqual(expected_header, "Splunk MySessionKeyForThisSession")

    def test_dispatch_with_ignore_saved_search_errors_true(self):
        """
        Test dispatch method to get value None in case of flag ignore_saved_search_errors=True
        """

        path = '/servicesNS/%s/%s/saved/searches/%s/dispatch' % ("admin", "search", "component")
        helper = SplunkClient(FakeInstanceConfig())

        # Mock the post response of request_session
        helper.requests_session.post = mock.MagicMock()
        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Not Found", "status_code": 404, "url": path})

        res = helper.dispatch(mocked_saved_search(), "search",
                              helper.instance_config.ignore_saved_search_errors, None)

        self.assertEqual(res, None)

    def test_dispatch_with_ignore_saved_search_errors_false(self):
        """
        Test dispatch method to get value None in case of flag ignore_saved_search_errors=False
        """

        path = '/servicesNS/%s/%s/saved/searches/%s/dispatch' % ("admin", "search", "component")
        helper = SplunkClient(FakeInstanceConfig())
        helper.instance_config.ignore_saved_search_errors = False

        # Mock the post response of request_session
        helper.requests_session.post = mock.MagicMock()
        helper.requests_session.post.return_value =\
            MockResponse({"reason": "Not Found", "status_code": 404, "url": path})

        self.assertRaises(HTTPError, helper.dispatch, mocked_saved_search(),
                          "search", helper.instance_config.ignore_saved_search_errors, None)

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

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_decode_token_util(self, mocked_decode_token):
        """
        Test token decoding utility
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        days = helper._decode_token_util("test", False)
        self.assertEqual(days, 27)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 0, "iat": 1584021915, "aud": "stackstate"})
    def test_decode_token_util_when_exp_set_never(self, mocked_decode_token):
        """
        Should return 999 days if first initial token expiration set to never
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        days = helper._decode_token_util("test", True)
        self.assertEqual(days, 999)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_is_token_expired_true(self, mocked_decode_token):
        """
        Test token validation method for invalid token
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 6, 20, 15, 44, 51)
        valid = helper._is_token_expired("test")
        # Token is expired
        self.assertTrue(valid)
        self.assertEqual(valid, True)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_is_token_expired_false(self, mocked_decode_token):
        """
        Test token validation method for invalid token
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        valid = helper._is_token_expired("test")
        # Token is not expired
        self.assertFalse(valid)
        self.assertEqual(valid, False)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_need_renewal_true(self, mocked_decode_token):
        """
        Test need renewal method when is_initial_token flag is True and should return True
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        valid = helper._need_renewal("test", True)
        # Need renewal should return True since flag is true
        self.assertTrue(valid)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_need_renewal_false(self, mocked_decode_token):
        """
        Test need renewal method when is_initial_token is false and should return False
        """
        helper = SplunkClient(FakeInstanceConfig())
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        valid = helper._need_renewal("test")
        # Need renewal should return True since flag is true
        self.assertFalse(valid)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_create_auth_token(self, mocked_response):
        """
        Test token creation method for initial token
        """
        new_token = json.loads(mocked_token_create_response()).get('entry')[0].get('content').get('token')

        helper = SplunkClient(FakeInstanceConfig())
        generated_token = helper._create_auth_token("test")
        username = helper.instance_config.username
        audience = helper.instance_config.audience
        expiry_days = helper.instance_config.token_expiration_days
        payload = {'name': username, 'audience': audience, 'expires_on': "+{}d".format(str(expiry_days))}
        mocked_response.assert_called_with("/services/authorization/tokens?output_mode=json", payload, 10)
        mocked_response.assert_called_once()

        # New token from response and generated token should be same
        self.assertEqual(generated_token, new_token)
        # Initial token and new token should differ
        self.assertNotEqual("test", new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session(self, mocked_decode_token):
        """
        Test token_auth_session when memory token is valid and doesn't need renewal
        """
        # load a token in memory for validation
        status = SplunkPersistentState({})
        status.set_auth_token('memorytokenpresent')
        config = FakeInstanceConfig()
        config.auth_type = AuthType.TokenAuth

        helper = SplunkClient(config)
        # update headers with memory token
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        helper.auth_session(status)

        # Header should be still with the memory token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format("memorytokenpresent"))

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    @mock.patch('stackstate_checks.splunk.client.splunk_client.SplunkClient._do_post',
                return_value=FakeResponse(mocked_token_create_response(), headers={}))
    def test_token_auth_session_need_renewal_initial_token(self, mocked_decode_token, moccked_post):
        """
        Test token_auth_session when initial token need to be refreshed
        """
        new_token = json.loads(mocked_token_create_response()).get('entry')[0].get('content').get('token')

        status = SplunkPersistentState({})
        config = FakeInstanceConfig()
        config.auth_type = AuthType.TokenAuth

        helper = SplunkClient(config)
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 5, 14, 15, 44, 51)
        helper._token_auth_session(status)

        # Header should be updated with the new token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format(new_token))
        # persistence data will have new updated token
        self.assertEqual(status.get_auth_token(), new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
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
        config = FakeInstanceConfig()
        config.auth_type = AuthType.TokenAuth

        helper = SplunkClient(config)
        helper.requests_session.headers.update({'Authorization': "Bearer memorytokenpresent"})
        helper._current_time = mock.MagicMock()
        helper._current_time.return_value = datetime.datetime(2020, 6, 5, 15, 44, 51)
        helper.auth_session(status)

        # Header should be updated with the new token
        expected_header = helper.requests_session.headers.get("Authorization")
        self.assertEqual(expected_header, "Bearer {}".format(new_token))
        # persistence data will have new token as well
        self.assertEqual(status.get_auth_token(), new_token)

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session_invalid_initial_token(self, mocked_decode_token):
        """
        Test token_auth_session to throw TokenExpiredException when initial token is expired
        """
        status = SplunkPersistentState({})
        config = FakeInstanceConfig()
        config.auth_type = AuthType.TokenAuth

        helper = SplunkClient(config)
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

    @mock.patch('stackstate_checks.splunk.client.splunk_client.jwt.decode',
                return_value={"exp": 1591797915, "iat": 1584021915, "aud": "stackstate"})
    def test_token_auth_session_invalid_memory_token(self, mocked_decode_token):
        """
        Test token_auth_session to throw TokenExpiredException when memory token is expired
        """
        status = SplunkPersistentState({})
        # load a token in memory for validation
        status.set_auth_token('memorytokenpresent')
        config = FakeInstanceConfig()
        config.auth_type = AuthType.TokenAuth

        helper = SplunkClient(config)
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
