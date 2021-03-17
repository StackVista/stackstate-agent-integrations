import unittest
import requests_mock
import json
import six
from requests import Session, Request
from schematics.models import Model, DataError
from schematics.types import StringType, IntType, BooleanType
from stackstate_checks.utils.http_helper import HTTPHelper, HTTPRequestType, HTTPAuthenticationType, HTTPResponseType
from stackstate_checks.utils.http_helper import HTTPHelperRequestHandler, HTTPHelperSessionHandler, HTTPMethod
from stackstate_checks.utils.http_helper import HTTPHelperResponseHandler, HTTPHelperConnectionHandler, \
    HTTPHelperRequestModel, HTTPHelperModel, HTTPHelperConnectionModel, HTTPHelperSessionModel
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.util.retry import Retry

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


"""
 HTTP Helper Request Class
"""


class TestHTTPHelperRequestHandler(unittest.TestCase):
    """
    """

    def test_get_request_model(self):
        request_handler = HTTPHelperRequestHandler()
        model = request_handler.get_request_model()
        assert isinstance(model, HTTPHelperRequestModel)

        # Test the base model. This should fail as a few things are required
        try:
            request_handler.validate_request_model()
        except DataError as e:
            assert len(e.errors) == 2

    """
    """

    def test_create_request_object(self):
        HTTPHelperRequestHandler({"method": "GET", "url": "mock://test.com"}).create_request_object()

    """
    """

    def test_method(self):
        assert HTTPHelperRequestHandler({"method": "GET"}).get_request_model().method == "GET"
        assert HTTPHelperRequestHandler({"method": "RANDOM"}).get_request_model().method == "RANDOM"
        assert HTTPHelperRequestHandler({"method": "GET"}).validate_method() is True

        try:
            HTTPHelperRequestHandler().validate_method()
            assert False
        except ValueError:
            assert True

        try:
            assert HTTPHelperRequestHandler({
                "method": "RANDOM"
            }).validate_method()
            assert False

        except NotImplementedError:
            assert True

    """
    """

    def test_url(self):
        assert HTTPHelperRequestHandler({"url": "http://mock.com"}).get_request_model().url == "http://mock.com"
        # TODO: Fix
        # assert HTTPHelperRequestHandler({"url": "http://mock.com?a=1"}).get_request_model().url == "http://mock.com"
        assert HTTPHelperRequestHandler({"url": "http://mock.com"}).validate_url() is True

        try:
            HTTPHelperRequestHandler().validate_url()
            assert False
        except ValueError:
            assert True

        try:
            HTTPHelperRequestHandler(-1).validate_url()
            assert False
        except TypeError:
            assert True

    """
    """

    def test_query_parameters(self):
        assert HTTPHelperRequestHandler().validate_query_param() is True
        assert HTTPHelperRequestHandler({"query": {"a": "1"}}).get_request_model().query == {"a": "1"}
        assert HTTPHelperRequestHandler({"query": {}}).get_request_model().query == {}
        assert HTTPHelperRequestHandler({"query": {"a": "1"}}).validate_query_param() is True
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    """
    """

    def test_body(self):
        assert HTTPHelperRequestHandler().validate_body() is True
        assert HTTPHelperRequestHandler({"body": {"a": "1"}}).get_request_model().body == {"a": "1"}
        assert HTTPHelperRequestHandler({"body": -1}).get_request_model().body == -1
        assert HTTPHelperRequestHandler({"body": -1}).validate_body() is True

    """
    """

    def test_headers(self):
        assert HTTPHelperRequestHandler().validate_headers() is True
        assert HTTPHelperRequestHandler({"headers": {"a": "1"}}).get_request_model().headers == {"a": "1"}
        assert HTTPHelperRequestHandler({"headers": {}}).get_request_model().headers == {}
        assert HTTPHelperRequestHandler({"headers": {"a": "1"}}).validate_headers() is True
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    """
    """

    def test_authentication(self):
        auth_valid = HTTPHelperRequestHandler({
            "auth_type": HTTPAuthenticationType.BasicAuth,
            "auth_data": {"username": "test", "password": "test"}
        })
        assert auth_valid.get_request_model().auth_data == {"username": "test", "password": "test"}
        assert auth_valid.get_request_model().auth_type == HTTPAuthenticationType.BasicAuth

        auth_invalid = HTTPHelperRequestHandler({
            "auth_type": -1,
            "auth_data": {}
        })
        assert auth_invalid.get_request_model().auth_data == {}
        assert auth_invalid.get_request_model().auth_type == -1

        assert auth_valid.validate_auth() is True
        try:
            assert auth_invalid.validate_auth() is True
            assert False
        except TypeError:
            assert True

    """
    """

    def test_body_type_validation(self):
        assert HTTPHelperRequestHandler().validate_body_type() is True
        assert HTTPHelperRequestHandler({"request_type_validation": HTTPRequestType.JSON}) \
                   .get_request_model().request_type_validation == HTTPRequestType.JSON
        assert HTTPHelperRequestHandler({"request_type_validation": -1}) \
                   .get_request_model().request_type_validation == -1
        assert HTTPHelperRequestHandler({
            "body": {},
            "request_type_validation": HTTPRequestType.JSON
        }).validate_body_type()
        try:
            assert HTTPHelperRequestHandler({
                "request_type_validation": HTTPRequestType.JSON
            }).validate_body_type()
            assert False
        except ValueError:
            assert True

    """
    """

    def test_body_schematic_validation(self):
        assert HTTPHelperRequestHandler().validate_body_schematic() is True
        assert HTTPHelperRequestHandler({"request_schematic_validation": BodyRequestSchematicTest}) \
                   .get_request_model().request_schematic_validation == BodyRequestSchematicTest
        assert HTTPHelperRequestHandler({"request_schematic_validation": -1}) \
                   .get_request_model().request_schematic_validation == -1
        assert HTTPHelperRequestHandler({
            "body": {
                "hello": "world",
                "pong": True
            },
            "request_schematic_validation": BodyRequestSchematicTest
        }).validate_body_schematic()
        try:
            assert HTTPHelperRequestHandler({
                "body": {},
                "request_schematic_validation": BodyRequestSchematicTest
            }).validate_body_schematic()
            assert False
        except TypeError:
            assert True


class TestHTTPHelperSessionHandler(unittest.TestCase):
    """
    """

    def test_get_session_model(self):
        session_handler = HTTPHelperSessionHandler()
        model = session_handler.get_session_model()
        assert isinstance(model, HTTPHelperSessionModel)

        session_handler.validate_session_model()

    """
    """

    def test_create_session_object(self):
        HTTPHelperSessionHandler({}).create_session_object()

    """
    """

    def test_headers(self):
        assert HTTPHelperSessionHandler().validate_headers() is True
        assert HTTPHelperSessionHandler({"headers": {"a": "1"}}).get_session_model().headers == {"a": "1"}
        assert HTTPHelperSessionHandler({"headers": {}}).get_session_model().headers == {}
        assert HTTPHelperSessionHandler({"headers": {"a": "1"}}).validate_headers() is True
        # There is no fail clause as you are unable to pass anything else than a dict or the schematic will complain

    """
    """

    def test_authentication(self):
        auth_valid = HTTPHelperSessionHandler({
            "auth_type": HTTPAuthenticationType.BasicAuth,
            "auth_data": {"username": "test", "password": "test"}
        })
        assert auth_valid.get_session_model().auth_data == {"username": "test", "password": "test"}
        assert auth_valid.get_session_model().auth_type == HTTPAuthenticationType.BasicAuth

        auth_invalid = HTTPHelperSessionHandler({
            "auth_type": -1,
            "auth_data": {}
        })
        assert auth_invalid.get_session_model().auth_data == {}
        assert auth_invalid.get_session_model().auth_type == -1

        assert auth_valid.validate_auth() is True
        try:
            assert auth_invalid.validate_auth() is True
            assert False
        except TypeError:
            assert True


class TestHTTPHelperConnectionHandler(unittest.TestCase):
    """
    """

    def test_get_connection_model(self):
        connection_handler = HTTPHelperConnectionHandler()
        model = connection_handler.get_connection_model()
        assert isinstance(model, HTTPHelperConnectionModel)

        connection_handler.validate_connection_model()

    """
    """

    def test_timeout(self):
        assert HTTPHelperConnectionHandler({"timeout": 10}).get_connection_model().timeout == 10
        assert HTTPHelperConnectionHandler({"timeout": 10}).validate_timeout() is True
        try:
            HTTPHelperConnectionHandler({"timeout": "RANDOM"})
            assert False
        except DataError:
            assert True

        try:
            HTTPHelperConnectionHandler({"timeout": "RANDOM"}).validate_timeout()
            assert False
        except DataError:
            assert True

    """
    """

    def test_retry_policy(self):
        assert HTTPHelperConnectionHandler({"retry_policy": {}}).get_connection_model().retry_policy == {}
        assert HTTPHelperConnectionHandler({"retry_policy": 1}).get_connection_model().retry_policy == 1
        assert HTTPHelperConnectionHandler({"retry_policy": {}}).validate_retry_policy() is True
        try:
            HTTPHelperConnectionHandler({"retry_policy": {"random": 0}}).validate_retry_policy()
            assert False
        except TypeError:
            assert True

    """
    """

    def test_ssl_verify(self):
        assert HTTPHelperConnectionHandler({"ssl_verify": True}).get_connection_model().ssl_verify is True
        assert HTTPHelperConnectionHandler({"ssl_verify": -1}).get_connection_model().ssl_verify == -1
        assert HTTPHelperConnectionHandler({"ssl_verify": True}).validate_ssl_verify() is True
        try:
            HTTPHelperConnectionHandler({"ssl_verify": "-1"}).validate_ssl_verify()
            assert False
        except DataError:
            assert True

    """
    """

    def test_retry_policy(self):
        assert HTTPHelperConnectionHandler({"proxy": {}}).get_connection_model().proxy == {}
        assert HTTPHelperConnectionHandler({"proxy": 1}).get_connection_model().proxy == 1
        assert HTTPHelperConnectionHandler({"proxy": {}}).validate_proxy() is True
        try:
            HTTPHelperConnectionHandler({"proxy": 1}).validate_proxy()
            assert False
        except TypeError:
            assert True

    """
    """

    def test_send(self):
        assert True


class TestHTTPHelperResponseHandler(unittest.TestCase):
    """
    """

    def test_get_response_model(self):
        response_handler = HTTPHelperResponseHandler()
        model = response_handler.get_response_model()
        assert isinstance(model, HTTPHelperResponseHandler)
        response_handler.validate_response_model()

    """
    """

    def test_body_schematic_validation(self):
        assert HTTPHelperResponseHandler().validate_body_schematic() is True
        assert HTTPHelperResponseHandler({"request_schematic_validation": BodyRequestSchematicTest}) \
                   .get_request_model().request_schematic_validation == BodyRequestSchematicTest
        assert HTTPHelperResponseHandler({"request_schematic_validation": -1}) \
                   .get_request_model().request_schematic_validation == -1
        assert HTTPHelperResponseHandler({
            "body": {
                "hello": "world",
                "pong": True
            },
            "request_schematic_validation": BodyRequestSchematicTest
        }).validate_body_schematic()
        try:
            assert HTTPHelperResponseHandler({
                "body": {},
                "request_schematic_validation": BodyRequestSchematicTest
            }).validate_body_schematic()
            assert False
        except TypeError:
            assert True

    """
    """

    def test_body_type_validation(self):
        assert HTTPHelperResponseHandler().validate_body_type() is True
        assert HTTPHelperResponseHandler({"request_type_validation": HTTPRequestType.JSON}) \
                   .get_response_model().request_type_validation == HTTPRequestType.JSON
        assert HTTPHelperResponseHandler({"request_type_validation": -1}) \
                   .get_response_model().request_type_validation == -1
        assert HTTPHelperResponseHandler({
            "body": {},
            "request_type_validation": HTTPRequestType.JSON
        }).validate_body_type()
        try:
            assert HTTPHelperResponseHandler({
                "request_type_validation": HTTPRequestType.JSON
            }).validate_body_type()
            assert False
        except ValueError:
            assert True


class TestHTTPHelperBase(unittest.TestCase):
    def test_random(self):
        http = HTTPHelper()
        response = http.get({
            "url": "mock://test.com",
            "mock_enable": True,
            "mock_status": 200,
            "mock_response": {
                'hello': 'world'
            },
        })
        print("response", response)

# class TestHTTPHelperBase(unittest.TestCase):
#     def test_unicode_response(self):
#         unicode = u""
#         for i in range(5000):
#             unicode = unicode + chr(i)
#
#         request = HTTPHelper()
#         response = request.get(
#             mock=True,
#             mock_status=200,
#             mock_response=unicode,
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "GET"
#         assert data.status_code == 200
#
#         assert json.loads(data.content.decode(data.encoding)) == unicode
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a',
#                                         'Content-Length': '11',
#                                         'Content-Type': 'application/x-www-form-urlencoded'}
#
#     """
#         Tests for GET
#     """
#
#     def test_get_no_validation(self):
#         request = HTTPHelper()
#         response = request.get(
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "GET"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a',
#                                         'Content-Length': '11',
#                                         'Content-Type': 'application/x-www-form-urlencoded'}
#
#     def test_get_request_validation_success(self):
#         request = HTTPHelper()
#         response = request.get(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "GET"
#         assert data.status_code == 200
#         assert response.get("response") is not None
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_get_request_validation_type_failure(self):
#         request = HTTPHelper()
#         try:
#             request.get(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation="Random",
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world', 'pong': True},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_get_request_validation_schematic_failure(self):
#         request = HTTPHelper()
#         try:
#             request.get(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation=HTTPRequestType.JSON,
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world'},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_get_response_validation_success(self):
#         request = HTTPHelper()
#         response = request.get(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world', 'pong': True},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "GET"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert response.get("response") is not None
#         assert response.get("errors") is None
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_get_response_validation_failure(self):
#         request = HTTPHelper()
#         response = request.get(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=400,
#             mock_response="test",
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#
#         data = response.get("response")
#         assert data.request.method == "GET"
#         assert data.status_code == 400
#         assert data.content.decode(data.encoding) == "\"test\""
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is False
#         assert response.get("response") is not None
#         assert len(response.get("errors")) == 3
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     """
#         Tests for POST
#     """
#
#     def test_post_no_validation(self):
#         request = HTTPHelper()
#         response = request.post(
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "POST"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a', 'Content-Length': '11',
#                                                  'Content-Type': 'application/x-www-form-urlencoded'}
#
#     def test_post_request_validation_success(self):
#         request = HTTPHelper()
#         response = request.post(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "POST"
#         assert data.status_code == 200
#         assert response.get("response") is not None
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_post_request_validation_type_failure(self):
#         request = HTTPHelper()
#         try:
#             request.post(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation="Random",
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world', 'pong': True},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_post_request_validation_schematic_failure(self):
#         request = HTTPHelper()
#         try:
#             request.post(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation=HTTPRequestType.JSON,
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world'},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_post_response_validation_success(self):
#         request = HTTPHelper()
#         response = request.post(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world', 'pong': True},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "POST"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert response.get("response") is not None
#         assert response.get("errors") is None
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_post_response_validation_failure(self):
#         request = HTTPHelper()
#         response = request.post(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=400,
#             mock_response="test",
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#
#         data = response.get("response")
#         assert data.request.method == "POST"
#         assert data.status_code == 400
#         assert data.content.decode(data.encoding) == "\"test\""
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is False
#         assert response.get("response") is not None
#         assert len(response.get("errors")) == 3
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     """
#         Tests for PUT
#     """
#
#     def test_put_no_validation(self):
#         request = HTTPHelper()
#         response = request.put(
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PUT"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a', 'Content-Length': '11',
#                                                  'Content-Type': 'application/x-www-form-urlencoded'}
#
#     def test_put_request_validation_success(self):
#         request = HTTPHelper()
#         response = request.put(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PUT"
#         assert data.status_code == 200
#         assert response.get("response") is not None
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_put_request_validation_type_failure(self):
#         request = HTTPHelper()
#         try:
#             request.put(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation="Random",
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world', 'pong': True},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_put_request_validation_schematic_failure(self):
#         request = HTTPHelper()
#         try:
#             request.put(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation=HTTPRequestType.JSON,
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world'},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_put_response_validation_success(self):
#         request = HTTPHelper()
#         response = request.put(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world', 'pong': True},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PUT"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert response.get("response") is not None
#         assert response.get("errors") is None
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_put_response_validation_failure(self):
#         request = HTTPHelper()
#         response = request.put(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=400,
#             mock_response="test",
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#
#         data = response.get("response")
#         assert data.request.method == "PUT"
#         assert data.status_code == 400
#         assert data.content.decode(data.encoding) == "\"test\""
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is False
#         assert response.get("response") is not None
#         assert len(response.get("errors")) == 3
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     """
#         Tests for DELETE
#     """
#
#     def test_delete_no_validation(self):
#         request = HTTPHelper()
#         response = request.delete(
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "DELETE"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a', 'Content-Length': '11',
#                                                  'Content-Type': 'application/x-www-form-urlencoded'}
#
#     def test_delete_request_validation_success(self):
#         request = HTTPHelper()
#         response = request.delete(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "DELETE"
#         assert data.status_code == 200
#         assert response.get("response") is not None
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_delete_request_validation_type_failure(self):
#         request = HTTPHelper()
#         try:
#             request.delete(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation="Random",
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world', 'pong': True},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_delete_request_validation_schematic_failure(self):
#         request = HTTPHelper()
#         try:
#             request.delete(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation=HTTPRequestType.JSON,
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world'},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_delete_response_validation_success(self):
#         request = HTTPHelper()
#         response = request.delete(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world', 'pong': True},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "DELETE"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert response.get("response") is not None
#         assert response.get("errors") is None
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_delete_response_validation_failure(self):
#         request = HTTPHelper()
#         response = request.delete(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=400,
#             mock_response="test",
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#
#         data = response.get("response")
#         assert data.request.method == "DELETE"
#         assert data.status_code == 400
#         assert data.content.decode(data.encoding) == "\"test\""
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is False
#         assert response.get("response") is not None
#         assert len(response.get("errors")) == 3
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     """
#         Tests for PATCH
#     """
#
#     def test_patch_no_validation(self):
#         request = HTTPHelper()
#         response = request.patch(
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world'},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PATCH"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'header': 'a', 'Content-Length': '11',
#                                                  'Content-Type': 'application/x-www-form-urlencoded'}
#
#     def test_patch_request_validation_success(self):
#         request = HTTPHelper()
#         response = request.patch(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world'},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PATCH"
#         assert data.status_code == 200
#         assert response.get("response") is not None
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_patch_request_validation_type_failure(self):
#         request = HTTPHelper()
#         try:
#             request.patch(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation="Random",
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world', 'pong': True},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_patch_request_validation_schematic_failure(self):
#         request = HTTPHelper()
#         try:
#             request.patch(
#                 request_schematic_validation=BodyRequestSchematicTest,
#                 request_type_validation=HTTPRequestType.JSON,
#                 mock=True,
#                 mock_status=200,
#                 mock_response={'hello': 'world'},
#                 url="mock://test.com",
#                 body={'hello': 'world'},
#                 headers={'header': 'a'},
#                 query={'query': 'b'},
#                 timeout=30,
#                 retry_policy=dict(
#                     total=3
#                 ),
#             )
#             assert False
#         except TypeError:
#             assert True
#
#     def test_patch_response_validation_success(self):
#         request = HTTPHelper()
#         response = request.patch(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=200,
#             mock_response={'hello': 'world', 'pong': True},
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#         data = response.get("response")
#         assert data.request.method == "PATCH"
#         assert data.status_code == 200
#         assert json.loads(data.content.decode(data.encoding)).get("hello") == "world"
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is True
#         assert response.get("response") is not None
#         assert response.get("errors") is None
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
#
#     def test_patch_response_validation_failure(self):
#         request = HTTPHelper()
#         response = request.patch(
#             request_schematic_validation=BodyRequestSchematicTest,
#             request_type_validation=HTTPRequestType.JSON,
#             response_status_code_validation=200,
#             response_type_validation=HTTPResponseType.JSON,
#             response_schematic_validation=BodyResponseSchematicTest,
#             mock=True,
#             mock_status=400,
#             mock_response="test",
#             url="mock://test.com",
#             body={'hello': 'world', 'pong': True},
#             headers={'header': 'a'},
#             query={'query': 'b'},
#             timeout=30,
#             retry_policy=dict(
#                 total=3
#             ),
#         )
#
#         data = response.get("response")
#         assert data.request.method == "PATCH"
#         assert data.status_code == 400
#         assert data.content.decode(data.encoding) == "\"test\""
#         assert data.request.url == "mock://test.com"
#         assert response.get("valid") is False
#         assert response.get("response") is not None
#         assert len(response.get("errors")) == 3
#         assert data.request.headers == {'Content-Length': '21',
#                                                  'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
