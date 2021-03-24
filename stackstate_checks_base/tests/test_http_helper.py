# coding=utf-8

import unittest

import pytest
from schematics.models import Model, DataError
from schematics.types import StringType, IntType, BooleanType

from stackstate_checks.utils.http_helper import (HTTPHelper, HTTPRequestType, HTTPAuthenticationType, HTTPResponseType)
from stackstate_checks.utils.http_helper import HTTPHelperConnectionHandler, \
    HTTPHelperRequestModel, HTTPHelperConnectionModel, HTTPHelperSessionModel
from stackstate_checks.utils.http_helper import HTTPHelperRequestHandler, HTTPHelperSessionHandler

"""
Structures used within the test cases
"""


class BodySchematicTest(Model):
    hello = IntType(required=True)


class BodyRequestSchematicTest(Model):
    hello = StringType(required=True)
    pong = BooleanType(required=True)


class BodyResponseSchematicTest(Model):
    hello = StringType(required=True)
    pong = BooleanType(required=True)


class TestHTTPHelperBase(unittest.TestCase):
    """
     HTTP Helper Request Class
    """
    def test_compact_unicode_response(self):
        http = HTTPHelper()
        http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': "Klüft skräms inför på fédéral électoral große",
                '頁設是': "頁設是煵엌嫠쯦案煪㍱從つ浳浤搰㍭煤洳橱橱迎事網計簡大㍵畱煵田煱둻睤㌹楤ぱ椹ぱ頹",
            },
        })
        # unicode_json_response.get_json()
        # self.assertEqual(unicode_json_response.get_json(), {
        #     'hello': u"Klüft skräms inför på fédéral électoral große",
        #     '頁設是': u"頁設是煵엌嫠쯦案煪㍱從つ浳浤搰㍭煤洳橱橱迎事網計簡大㍵畱煵田煱둻睤㌹楤ぱ椹ぱ頹",
        # })

    def test_full_get(self):
        http = HTTPHelper()
        result = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
            "auth_data": {
                'username': 'world',
                'password': 'hello'
            },
            "auth_type": HTTPRequestType.JSON,
            "session_auth_data": {
                'username': 'world',
                'password': 'hello'
            },
            "session_auth_type": HTTPRequestType.JSON,
            "body": {"hello": "world", "pong": True},
            "proxy": {"hello": "world"},
            "headers": {"a": "1"},
            "session_headers": {"b": "1"},
            "query": {"c": "1"},
            "timeout": 30,
            "ssl_verify": True,
            "retry_policy": {},
            "request_schematic_validation": BodyRequestSchematicTest,
            "request_type_validation": HTTPRequestType.JSON,
            "response_status_code_validation": 200,
            "response_type_validation": HTTPResponseType.JSON,
            "response_schematic_validation": BodyResponseSchematicTest,
        })

        self.assertEqual(result.get_request_method(), "GET")
        self.assertEqual(result.get_status_code(), 200)
        self.assertEqual(result.get_json(), {
            'hello': 'world',
            'pong': True,
        })
        self.assertEqual(result.get_request_url(), "mock://test.com")
        self.assertEqual(result.get_request_headers(), {'a': '1',
                                                        'Content-Length': '21',
                                                        'Content-Type': 'application/x-www-form-urlencoded'})

    def test_compact_get(self):
        http = HTTPHelper()
        result = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 201,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })

        self.assertEqual(result.get_request_method(), "GET")
        self.assertEqual(result.get_status_code(), 201)
        self.assertEqual(result.get_json(), {
            'hello': 'world',
            'pong': True,
        })
        self.assertEqual(result.get_request_url(), "mock://test.com")

    def test_full_unicode_request_and_response(self):
        unicode = ""
        for i in range(100):
            unicode = unicode + chr(i)

        http = HTTPHelper()
        result = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": unicode,
            "auth_data": {
                'username': 'world',
                'password': 'hello'
            },
            "auth_type": HTTPRequestType.JSON,
            "session_auth_data": {
                'username': 'world',
                'password': 'hello'
            },
            "session_auth_type": HTTPRequestType.JSON,
            "body": unicode,
            "proxy": {"hello": "world"},
            "headers": {"a": "1"},
            "session_headers": {"b": "1"},
            "query": {"c": "1"},
            "timeout": 30,
            "ssl_verify": True,
            "retry_policy": {},
            "response_status_code_validation": 200,
        })

        self.assertEqual(result.get_request_method(), "GET")
        self.assertEqual(result.get_status_code(), 200)
        self.assertEqual(result.get_request_url(), "mock://test.com")
        self.assertEqual(result.get_request_headers(), {'a': '1', 'Content-Length': '100'})


class TestHTTPHelperRequestHandler(unittest.TestCase):
    def test_get_request_model(self):
        request_handler = HTTPHelperRequestHandler()
        model = request_handler.get_request_model()
        self.assertTrue(isinstance(model, HTTPHelperRequestModel))

        with pytest.raises(DataError):
            request_handler.validate_request_model()

    def test_create_request_object(self):
        HTTPHelperRequestHandler({"method": "GET",
                                  "endpoint": "mock://test.com"}).create_request_object()

    def test_method(self):
        self.assertEqual(HTTPHelperRequestHandler({"method": "GET"}).get_request_model().method, "GET")
        self.assertEqual(HTTPHelperRequestHandler({"method": "RANDOM"}).get_request_model().method, "RANDOM")
        self.assertTrue(HTTPHelperRequestHandler({"method": "GET"}).validate_method())

        with pytest.raises(ValueError):
            HTTPHelperRequestHandler().validate_method()

        with pytest.raises(NotImplementedError):
            HTTPHelperRequestHandler({"method": "RANDOM"}).validate_method()

    def test_url(self):
        self.assertEqual(HTTPHelperRequestHandler({"endpoint": "http://mock.com"}).get_request_model().endpoint,
                         "http://mock.com")
        self.assertTrue(HTTPHelperRequestHandler({"endpoint": "http://mock.com"}).validate_endpoint())

        with pytest.raises(ValueError):
            HTTPHelperRequestHandler().validate_endpoint()

        with pytest.raises(TypeError):
            HTTPHelperRequestHandler(-1).validate_endpoint()

    def test_query_parameters(self):
        self.assertTrue(HTTPHelperRequestHandler().validate_query_param())
        self.assertEqual(HTTPHelperRequestHandler({"query": {"a": "1"}}).get_request_model().query, {"a": "1"})
        self.assertEqual(HTTPHelperRequestHandler({"query": {}}).get_request_model().query, {})
        self.assertTrue(HTTPHelperRequestHandler({"query": {"a": "1"}}).validate_query_param())
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    def test_body(self):
        self.assertTrue(HTTPHelperRequestHandler().validate_body())
        self.assertEqual(HTTPHelperRequestHandler({"body": {"a": "1"}}).get_request_model().body, {"a": "1"})
        self.assertEqual(HTTPHelperRequestHandler({"body": -1}).get_request_model().body, -1)
        self.assertTrue(HTTPHelperRequestHandler({"body": -1}).validate_body())

    def test_headers(self):
        self.assertTrue(HTTPHelperRequestHandler().validate_headers())
        self.assertEqual(HTTPHelperRequestHandler({"headers": {"a": "1"}}).get_request_model().headers, {"a": "1"})
        self.assertEqual(HTTPHelperRequestHandler({"headers": {}}).get_request_model().headers, {})
        self.assertTrue(HTTPHelperRequestHandler({"headers": {"a": "1"}}).validate_headers())
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    def test_authentication(self):
        auth_valid = HTTPHelperRequestHandler({
            "auth_type": HTTPAuthenticationType.BasicAuth,
            "auth_data": {"username": "test", "password": "test"}
        })
        self.assertEqual(auth_valid.get_request_model().auth_data, {"username": "test", "password": "test"})
        self.assertEqual(auth_valid.get_request_model().auth_type, HTTPAuthenticationType.BasicAuth)

        auth_invalid = HTTPHelperRequestHandler({
            "auth_type": -1,
            "auth_data": {}
        })
        self.assertEqual(auth_invalid.get_request_model().auth_data, {})
        self.assertEqual(auth_invalid.get_request_model().auth_type, -1)
        self.assertTrue(auth_valid.validate_auth())
        with pytest.raises(TypeError):
            auth_invalid.validate_auth()

    def test_body_type_validation(self):
        self.assertTrue(HTTPHelperRequestHandler().validate_body_type())
        self.assertEqual(HTTPHelperRequestHandler({"request_type_validation": HTTPRequestType.JSON})
                         .get_request_model().request_type_validation, HTTPRequestType.JSON)
        self.assertEqual(HTTPHelperRequestHandler({"request_type_validation": -1})
                         .get_request_model().request_type_validation, -1)
        self.assertTrue(HTTPHelperRequestHandler({
            "body": {},
            "request_type_validation": HTTPRequestType.JSON
        }).validate_body_type())

        with pytest.raises(ValueError):
            HTTPHelperRequestHandler({
                "request_type_validation": HTTPRequestType.JSON
            }).validate_body_type()

    def test_body_schematic_validation(self):
        self.assertTrue(HTTPHelperRequestHandler().validate_body_schematic())
        self.assertEqual(HTTPHelperRequestHandler({"request_schematic_validation": BodyRequestSchematicTest})
                         .get_request_model().request_schematic_validation, BodyRequestSchematicTest)
        self.assertEqual(HTTPHelperRequestHandler({"request_schematic_validation": -1})
                         .get_request_model().request_schematic_validation, -1)
        self.assertTrue(HTTPHelperRequestHandler({
            "body": {
                "hello": "world",
                "pong": True
            },
            "request_schematic_validation": BodyRequestSchematicTest
        }).validate_body_schematic())

        with pytest.raises(DataError):
            HTTPHelperRequestHandler({
                "body": {},
                "request_schematic_validation": BodyRequestSchematicTest
            }).validate_body_schematic()


class TestHTTPHelperSessionHandler(unittest.TestCase):
    def test_get_session_model(self):
        session_handler = HTTPHelperSessionHandler()
        model = session_handler.get_session_model()
        self.assertTrue(isinstance(model, HTTPHelperSessionModel))

        session_handler.validate_session_model()

    def test_create_session_object(self):
        HTTPHelperSessionHandler({}).create_session_object()

    def test_headers(self):
        self.assertTrue(HTTPHelperSessionHandler().validate_headers())
        self.assertEqual(HTTPHelperSessionHandler({"headers": {"a": "1"}}).get_session_model().headers, {"a": "1"})
        self.assertEqual(HTTPHelperSessionHandler({"headers": {}}).get_session_model().headers, {})
        self.assertTrue(HTTPHelperSessionHandler({"headers": {"a": "1"}}).validate_headers())
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    def test_authentication(self):
        auth_valid = HTTPHelperSessionHandler({
            "auth_type": HTTPAuthenticationType.BasicAuth,
            "auth_data": {"username": "test", "password": "test"}
        })
        self.assertEqual(auth_valid.get_session_model().auth_data, {"username": "test", "password": "test"})
        self.assertEqual(auth_valid.get_session_model().auth_type, HTTPAuthenticationType.BasicAuth)

        auth_invalid = HTTPHelperSessionHandler({
            "auth_type": -1,
            "auth_data": {}
        })
        self.assertEqual(auth_invalid.get_session_model().auth_data, {})
        self.assertEqual(auth_invalid.get_session_model().auth_type, -1)
        self.assertTrue(auth_valid.validate_auth())

        with pytest.raises(TypeError):
            auth_invalid.validate_auth()


class TestHTTPHelperConnectionHandler(unittest.TestCase):
    def test_get_connection_model(self):
        connection_handler = HTTPHelperConnectionHandler()
        model = connection_handler.get_connection_model()
        self.assertTrue(isinstance(model, HTTPHelperConnectionModel))

        connection_handler.validate_connection_model()

    def test_timeout(self):
        self.assertEqual(HTTPHelperConnectionHandler({"timeout": 10}).get_connection_model().timeout, 10)
        self.assertTrue(HTTPHelperConnectionHandler({"timeout": 10}).validate_timeout())

        with pytest.raises(DataError):
            HTTPHelperConnectionHandler({"timeout": "RANDOM"})

        with pytest.raises(DataError):
            HTTPHelperConnectionHandler({"timeout": "RANDOM"}).validate_timeout()

    def test_retry_policy(self):
        self.assertEqual(HTTPHelperConnectionHandler({"retry_policy": {}}).get_connection_model().retry_policy, {})
        self.assertEqual(HTTPHelperConnectionHandler({"retry_policy": 1}).get_connection_model().retry_policy, 1)
        self.assertTrue(HTTPHelperConnectionHandler({"retry_policy": {}}).validate_retry_policy())
        with pytest.raises(TypeError):
            HTTPHelperConnectionHandler({"retry_policy": {"random": 0}}).validate_retry_policy()

    def test_ssl_verify(self):
        self.assertTrue(HTTPHelperConnectionHandler({"ssl_verify": True}).get_connection_model().ssl_verify)
        self.assertTrue(HTTPHelperConnectionHandler({"ssl_verify": True}).validate_ssl_verify())
        with pytest.raises(DataError):
            HTTPHelperConnectionHandler({"ssl_verify": "-1"}).validate_ssl_verify()

    def test_retry_proxy(self):
        self.assertEqual(HTTPHelperConnectionHandler({"proxy": {}}).get_connection_model().proxy, {})
        self.assertEqual(HTTPHelperConnectionHandler({"proxy": 1}).get_connection_model().proxy, 1)
        self.assertTrue(HTTPHelperConnectionHandler({"proxy": {}}).validate_proxy())
        with pytest.raises(TypeError):
            HTTPHelperConnectionHandler({"proxy": 1}).validate_proxy()


class TestHTTPHelperResponseHandler(unittest.TestCase):
    def test_get_status_code(self):
        http = HTTPHelper()
        response = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })
        self.assertEqual(response.get_status_code(), 200)

    def test_get_json(self):
        http = HTTPHelper()
        response = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })
        self.assertEqual(response.get_json(), {
            'hello': 'world',
            'pong': True,
        })

    def test_get_request_method(self):
        http = HTTPHelper()
        response = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })
        self.assertEqual(response.get_request_method(), "GET")

    def test_get_request_url(self):
        http = HTTPHelper()
        response = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })
        self.assertEqual(response.get_request_url(), "mock://test.com")

    def test_get_request_headers(self):
        http = HTTPHelper()
        response = http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
        })
        self.assertEqual(response.get_request_headers(), {})

    def test_body_schematic_validation(self):
        http = HTTPHelper()
        http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
            "response_schematic_validation": BodyResponseSchematicTest,
        })

        with pytest.raises(ValueError):
            http.get({
                "endpoint": "mock://test.com",
                "mock_enable": True,
                "mock_status": 200,
                "mock_json": "test",
                "response_schematic_validation": BodyResponseSchematicTest,
            })

    def test_body_type_validation(self):
        http = HTTPHelper()
        http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
            "response_type_validation": HTTPResponseType.JSON,
        })

        with pytest.raises(ValueError):
            http.get({
                "endpoint": "mock://test.com",
                "mock_enable": True,
                "mock_status": 200,
                "mock_json": "test",
                "response_type_validation": HTTPResponseType.JSON,
            })

    def test_status_code_validation(self):
        http = HTTPHelper()
        http.get({
            "endpoint": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_json": {
                'hello': 'world',
                'pong': True,
            },
            "response_status_code_validation": 200,
        })

        with pytest.raises(ValueError):
            http.get({
                "endpoint": "mock://test.com",
                "mock_enable": True,
                "mock_status": 201,
                "mock_json": "test",
                "response_status_code_validation": 200,
            })
