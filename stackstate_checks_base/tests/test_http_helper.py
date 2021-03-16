import unittest
import requests_mock
import json
import six
from requests import Session, Request
from schematics.models import Model
from schematics.types import StringType, IntType, BooleanType
from stackstate_checks.utils.http_helper import HTTPHelper, HTTPRequestType, HTTPAuthenticationType, HTTPResponseType
from stackstate_checks.utils.http_helper import HTTPHelperRequestHandler, HTTPHelperSessionHandler, HTTPMethod
from stackstate_checks.utils.http_helper import HTTPHelperResponseHandler, HTTPHelperConnectionHandler, HTTPHelperCommon
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
 HTTP Helper Common Class
"""


class TestHTTPHelperCommon(unittest.TestCase):
    verbose = True

    def test_print_error(self):
        try:
            HTTPHelperCommon().print_error("Error Message")
            assert False
        except Exception as e:
            assert str(e) == "Error Message"

    def test_print_not_implemented_error(self):
        try:
            HTTPHelperCommon().print_not_implemented_error("Error Message")
            assert False
        except NotImplementedError as e:
            assert str(e) == "Error Message"

    def test_print_type_error(self):
        try:
            HTTPHelperCommon().print_type_error("Error Message")
            assert False
        except TypeError as e:
            assert str(e) == "Error Message"

    def test_print_value_error(self):
        try:
            HTTPHelperCommon().print_value_error("Error Message")
            assert False
        except ValueError as e:
            assert str(e) == "Error Message"

    def test_split_string_into_dict(self):
        result = HTTPHelperCommon().split_string_into_dict("", "&", "=")
        assert result == {}

        result = HTTPHelperCommon().split_string_into_dict("hello=world", "&", "=")
        assert result == {'hello': 'world'}

        result = HTTPHelperCommon().split_string_into_dict("hello=world&test=123", "&", "=")
        assert result == {'hello': 'world', 'test': '123'}


"""
 HTTP Helper Request Class
"""


class TestHTTPHelperRequestHandler(unittest.TestCase):
    verbose = True

    """
        Test the main request object which is the equivalent of the Request() object
    """
    def test_request_main_object(self):
        req = HTTPHelperRequestHandler(self.verbose)

        # Default Test
        assert isinstance(req.get_request(), type(Request()))

        # Test setting a invalid request object
        try:
            req.set_request(False)
            assert False
        except TypeError:
            assert True

        # Test setting a valid request object
        req.set_request(Request())
        assert isinstance(req.get_request(), type(Request()))

        # Reset the request object
        req.reset_request()
        assert isinstance(req.get_request(), type(Request()))

    """
        Test the HTTP method for example GET or POST
    """
    def test_method(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_method() is None

        # Test direct string
        req.set_method("GET")
        assert req.get_method() == "GET"

        # Test enum
        req.set_method(HTTPMethod.PUT)
        assert req.get_method() == "PUT"

        # Test clear
        req.clear_method()
        assert req.get_method() is None

        # Not implemented
        try:
            req.set_method("RANDOM")
            assert False
        except NotImplementedError:
            assert True

    """
        Test the HTTP endpoint for example http://www.google.com
    """
    def test_url(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_url() is None

        # Test valid URL
        req.set_url("http://www.google.com")
        assert req.get_url() == "http://www.google.com"

        # Test clearing URL
        req.clear_url()
        assert req.get_url() is None

        # Test valid URL + Query Parameters
        req.set_url("http://www.google.com?hello=world")
        assert req.get_url() == "http://www.google.com"

        # Invalid URL
        try:
            req.set_url(-1)
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP query parameters for example http://www.google.com?hello=world and direct apply
    """
    def test_query_parameters(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_url() is None

        # Test valid Query Parameters
        req.set_query_param({
            "hello": "world"
        })
        assert req.get_query_param() == {'hello': 'world'}

        # Test clearing Query Parameters
        req.clear_query_param()
        assert req.get_query_param() is None

        # Test valid URL + Query Parameters
        req.set_url("http://www.google.com?hello=world")
        assert req.get_query_param() == {'hello': 'world'}

        # Invalid Query Parameters
        try:
            req.set_query_param(-1)
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP body for example {'hello': 'world'}
    """
    def test_body(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert len(req.get_body()) == 0

        # Test valid JSON Body
        req.set_body({
            "hello": "world"
        })
        assert req.get_body() == {'hello': 'world'}

        # Test valid Plain Body
        req.set_body("test")
        assert req.get_body() == "test"

        # Test clearing Body
        req.clear_body()
        assert len(req.get_body()) == 0

    """
        Test the HTTP headers for example {'hello': 'world'}
    """
    def test_headers(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert len(req.get_headers()) == 0

        # Test valid Headers
        req.set_headers({
            "hello": "world"
        })
        assert req.get_headers() == {'hello': 'world'}

        # Test clearing Headers
        req.clear_headers()
        assert len(req.get_headers()) == 0

        # Invalid Headers
        try:
            req.set_headers(-1)
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP authentication for example {'username': 'hello', 'password': 'world'}
    """
    def test_authentication(self):
        # Default Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_auth() is None

        # Test valid Auth
        req.set_auth(HTTPAuthenticationType.BasicAuth, {
            "username": "hello",
            "password": "world",
        })
        assert req.get_auth() == HTTPBasicAuth("hello", "world")

        # Test invalid Auth type
        try:
            req.set_auth("Random", {
                "username": "hello",
                "password": "world",
            })
            assert False
        except TypeError:
            assert True

        # Test invalid Auth data
        try:
            req.set_auth(HTTPAuthenticationType.BasicAuth, {
                "username": "hello",
            })
            assert False
        except TypeError:
            assert True

        # Test clearing Auth
        req.clear_auth()
        assert req.get_auth() is None

    """
        Test the HTTP Request body validation
    """
    def test_body_type_validation(self):
        # Default Validation Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_body_type_validation() is None

        # Set body validation
        req = HTTPHelperRequestHandler(self.verbose)
        req.set_body_type_validation(HTTPRequestType.JSON)
        assert req.get_body_type_validation() is HTTPRequestType.JSON

        # Set invalid body validation
        req = HTTPHelperRequestHandler(self.verbose)
        try:
            req.set_body_type_validation('Test')
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP Request body validation
    """
    def test_body_schematic_validation(self):
        # Default Validation Test
        req = HTTPHelperRequestHandler(self.verbose)
        assert req.get_body_schematic_validation() is None

        # Set body validation
        req = HTTPHelperRequestHandler(self.verbose)
        req.set_body_schematic_validation(BodySchematicTest)
        assert req.get_body_schematic_validation() is BodySchematicTest

        # Set invalid body validation
        req = HTTPHelperRequestHandler(self.verbose)
        try:
            req.set_body_schematic_validation('Test')
            assert False
        except TypeError:
            assert True


class TestHTTPHelperSessionHandler(unittest.TestCase):
    verbose = True

    """
        Test the main request object which is the equivalent of the Request() object
    """
    def test_session_main_object(self):
        req = HTTPHelperSessionHandler(self.verbose)

        # Default Test
        assert isinstance(req.get_session(), type(Session()))

        # Test setting a invalid request object
        try:
            req.set_session(False)
            assert False
        except TypeError:
            assert True

        # Test setting a valid request object
        req.set_session(Session())
        assert isinstance(req.get_session(), type(Session()))

        # Reset the request object
        req.reset_session()
        assert isinstance(req.get_session(), type(Session()))

    """
        Test the HTTP query parameters for example http://www.google.com?hello=world and direct apply
    """
    def test_query_parameters(self):
        # Default Test
        req = HTTPHelperSessionHandler(self.verbose)

        # Test valid Query Parameters
        req.set_query_param({
            "hello": "world"
        })
        assert req.get_query_param() == {'hello': 'world'}

        # Test clearing Query Parameters
        req.clear_query_param()
        assert len(req.get_query_param()) == 0

        # Invalid Query Parameters
        try:
            req.set_query_param(-1)
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP headers for example {'hello': 'world'}
    """
    def test_headers(self):
        # Default Test
        req = HTTPHelperSessionHandler(self.verbose)
        assert len(req.get_headers()) == 4
        assert req.get_headers() == {'User-Agent': 'python-requests/2.24.0', 'Accept-Encoding': 'gzip, deflate',
                                     'Accept': '*/*', 'Connection': 'keep-alive'}

        # Test valid Headers
        req.set_headers({
            "hello": "world"
        })
        assert req.get_headers() == {'User-Agent': 'python-requests/2.24.0', 'Accept-Encoding': 'gzip, deflate',
                                     'Accept': '*/*', 'Connection': 'keep-alive', 'hello': 'world'}

        # Test clearing Headers
        req.clear_headers()
        assert len(req.get_headers()) == 0

        # Invalid Headers
        try:
            req.set_headers(-1)
            assert False
        except TypeError:
            assert True

    """
        Test the HTTP authentication for example {'username': 'hello', 'password': 'world'}
    """
    def test_authentication(self):
        # Default Test
        req = HTTPHelperSessionHandler(self.verbose)
        assert req.get_auth() is None

        # Test valid Auth
        req.set_auth(HTTPAuthenticationType.BasicAuth, {
            "username": "hello",
            "password": "world",
        })
        assert req.get_auth() == HTTPBasicAuth("hello", "world")

        # Test invalid Auth type
        try:
            req.set_auth("Random", {
                "username": "hello",
                "password": "world",
            })
            assert False
        except TypeError:
            assert True

        # Test invalid Auth data
        try:
            req.set_auth(HTTPAuthenticationType.BasicAuth, {
                "username": "hello",
            })
            assert False
        except TypeError:
            assert True

        # Test clearing Auth
        req.clear_auth()
        assert req.get_auth() is None


class TestHTTPHelperConnectionHandler(unittest.TestCase):
    verbose = True

    def test_timeout(self):
        # Default Test
        req = HTTPHelperConnectionHandler(self.verbose)
        assert req.get_timeout() is None

        # Default Valid
        req.set_timeout(10)
        assert req.get_timeout() == 10

        # Clear Timeout
        req.clear_timeout()
        assert req.get_timeout() is None

        # Invalid Timeout
        try:
            req.set_timeout("Random")
            assert False
        except TypeError:
            assert True

    def test_retry_policy(self):
        # Default Test
        req = HTTPHelperConnectionHandler(self.verbose)
        assert req.get_retry_policy() is None

        # Default Valid
        req.set_retry_policy(total=3)
        assert req.get_retry_policy().total == Retry(total=3).total

        # Clear Timeout
        req.clear_retry_policy()
        assert req.get_retry_policy() is None

        # Invalid Timeout
        try:
            req.set_retry_policy("Random")
            assert False
        except TypeError:
            assert True

    def test_ssl(self):
        # Default Test
        req = HTTPHelperConnectionHandler(self.verbose)
        assert req.get_ssl_verify() is True

        # Default Valid
        req.set_ssl_verify(False)
        assert req.get_ssl_verify() is False

        # Clear Timeout
        req.clear_ssl_verify()
        assert req.get_ssl_verify() is True

        # Invalid Timeout
        try:
            req.set_ssl_verify("Random")
            assert False
        except TypeError:
            assert True

    def test_proxy(self):
        # Default Test
        req = HTTPHelperConnectionHandler(self.verbose)
        assert req.get_proxy() is None

        # Default Valid
        req.set_proxy({
            'hello': 'world'
        })
        assert req.get_proxy() == {
            'hello': 'world'
        }

        # Clear Timeout
        req.clear_proxy()
        assert req.get_proxy() is None

        # Invalid Timeout
        try:
            req.set_proxy("Random")
            assert False
        except TypeError:
            assert True

    def test_send(self):
        # Default Test
        # Manual build objects
        req = HTTPHelperConnectionHandler(self.verbose)
        session = HTTPHelperSessionHandler()
        request = HTTPHelperRequestHandler()
        response = HTTPHelperResponseHandler()

        session.apply_mock("GET", "mock://test.com", 200, {"hello": "world"})
        request.set_url("mock://test.com")
        request.set_method("GET")

        res = req.send(session, request, response)
        res_data = res.get("response")

        assert res.get("valid") is True
        assert res_data.status_code == 200
        assert json.loads(res_data.content.decode(res_data.encoding)).get("hello") == "world"


class TestHTTPHelperBase(unittest.TestCase):
    verbose = True

    """
        Tests for GET
    """

    def test_get_no_validation(self):
        request = HTTPHelper(self.verbose)
        response = request.get(
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world'},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "GET"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'header': 'a', 'Content-Length': '11',
                                                 'Content-Type': 'application/x-www-form-urlencoded'}

    def test_get_request_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.get(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "GET"
        assert response_data.status_code == 200
        assert response.get("response") is not None
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_get_request_validation_type_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.get(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation="Random",
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world', 'pong': True},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_get_request_validation_schematic_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.get(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation=HTTPRequestType.JSON,
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world'},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_get_response_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.get(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world', 'pong': True},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "GET"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response.get("response") is not None
        assert response.get("errors") is None
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_get_response_validation_failure(self):
        request = HTTPHelper(self.verbose)
        response = request.get(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=400,
            mock_response="test",
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )

        response_data = response.get("response")
        assert response_data.request.method == "GET"
        assert response_data.status_code == 400
        assert response_data.content.decode(response_data.encoding) == "\"test\""
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is False
        assert response.get("response") is not None
        assert len(response.get("errors")) == 3
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    """
        Tests for POST
    """

    def test_post_no_validation(self):
        request = HTTPHelper(self.verbose)
        response = request.post(
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world'},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "POST"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'header': 'a', 'Content-Length': '11',
                                                 'Content-Type': 'application/x-www-form-urlencoded'}

    def test_post_request_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.post(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "POST"
        assert response_data.status_code == 200
        assert response.get("response") is not None
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_post_request_validation_type_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.post(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation="Random",
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world', 'pong': True},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_post_request_validation_schematic_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.post(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation=HTTPRequestType.JSON,
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world'},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_post_response_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.post(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world', 'pong': True},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "POST"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response.get("response") is not None
        assert response.get("errors") is None
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_post_response_validation_failure(self):
        request = HTTPHelper(self.verbose)
        response = request.post(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=400,
            mock_response="test",
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )

        response_data = response.get("response")
        assert response_data.request.method == "POST"
        assert response_data.status_code == 400
        assert response_data.content.decode(response_data.encoding) == "\"test\""
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is False
        assert response.get("response") is not None
        assert len(response.get("errors")) == 3
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    """
        Tests for PUT
    """

    def test_put_no_validation(self):
        request = HTTPHelper(self.verbose)
        response = request.put(
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world'},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PUT"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'header': 'a', 'Content-Length': '11',
                                                 'Content-Type': 'application/x-www-form-urlencoded'}

    def test_put_request_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.put(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PUT"
        assert response_data.status_code == 200
        assert response.get("response") is not None
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_put_request_validation_type_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.put(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation="Random",
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world', 'pong': True},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_put_request_validation_schematic_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.put(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation=HTTPRequestType.JSON,
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world'},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_put_response_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.put(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world', 'pong': True},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PUT"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response.get("response") is not None
        assert response.get("errors") is None
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_put_response_validation_failure(self):
        request = HTTPHelper(self.verbose)
        response = request.put(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=400,
            mock_response="test",
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )

        response_data = response.get("response")
        assert response_data.request.method == "PUT"
        assert response_data.status_code == 400
        assert response_data.content.decode(response_data.encoding) == "\"test\""
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is False
        assert response.get("response") is not None
        assert len(response.get("errors")) == 3
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    """
        Tests for DELETE
    """

    def test_delete_no_validation(self):
        request = HTTPHelper(self.verbose)
        response = request.delete(
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world'},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "DELETE"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'header': 'a', 'Content-Length': '11',
                                                 'Content-Type': 'application/x-www-form-urlencoded'}

    def test_delete_request_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.delete(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "DELETE"
        assert response_data.status_code == 200
        assert response.get("response") is not None
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_delete_request_validation_type_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.delete(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation="Random",
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world', 'pong': True},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_delete_request_validation_schematic_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.delete(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation=HTTPRequestType.JSON,
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world'},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_delete_response_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.delete(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world', 'pong': True},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "DELETE"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response.get("response") is not None
        assert response.get("errors") is None
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_delete_response_validation_failure(self):
        request = HTTPHelper(self.verbose)
        response = request.delete(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=400,
            mock_response="test",
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )

        response_data = response.get("response")
        assert response_data.request.method == "DELETE"
        assert response_data.status_code == 400
        assert response_data.content.decode(response_data.encoding) == "\"test\""
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is False
        assert response.get("response") is not None
        assert len(response.get("errors")) == 3
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    """
        Tests for PATCH
    """

    def test_patch_no_validation(self):
        request = HTTPHelper(self.verbose)
        response = request.patch(
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world'},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PATCH"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'header': 'a', 'Content-Length': '11',
                                                 'Content-Type': 'application/x-www-form-urlencoded'}

    def test_patch_request_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.patch(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world'},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PATCH"
        assert response_data.status_code == 200
        assert response.get("response") is not None
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_patch_request_validation_type_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.patch(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation="Random",
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world', 'pong': True},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_patch_request_validation_schematic_failure(self):
        request = HTTPHelper(self.verbose)
        try:
            request.patch(
                request_schematic_validation=BodyRequestSchematicTest,
                request_type_validation=HTTPRequestType.JSON,
                mock=True,
                mock_status=200,
                mock_response={'hello': 'world'},
                url="mock://www.google.com",
                body={'hello': 'world'},
                headers={'header': 'a'},
                query={'query': 'b'},
                timeout=30,
                retry_policy=dict(
                    total=3
                ),
            )
            assert False
        except TypeError:
            assert True

    def test_patch_response_validation_success(self):
        request = HTTPHelper(self.verbose)
        response = request.patch(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=200,
            mock_response={'hello': 'world', 'pong': True},
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )
        response_data = response.get("response")
        assert response_data.request.method == "PATCH"
        assert response_data.status_code == 200
        assert json.loads(response_data.content.decode(response_data.encoding)).get("hello") == "world"
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is True
        assert response.get("response") is not None
        assert response.get("errors") is None
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}

    def test_patch_response_validation_failure(self):
        request = HTTPHelper(self.verbose)
        response = request.patch(
            request_schematic_validation=BodyRequestSchematicTest,
            request_type_validation=HTTPRequestType.JSON,
            response_status_code_validation=200,
            response_type_validation=HTTPResponseType.JSON,
            response_schematic_validation=BodyResponseSchematicTest,
            mock=True,
            mock_status=400,
            mock_response="test",
            url="mock://www.google.com",
            body={'hello': 'world', 'pong': True},
            headers={'header': 'a'},
            query={'query': 'b'},
            timeout=30,
            retry_policy=dict(
                total=3
            ),
        )

        response_data = response.get("response")
        assert response_data.request.method == "PATCH"
        assert response_data.status_code == 400
        assert response_data.content.decode(response_data.encoding) == "\"test\""
        assert response_data.request.url == "mock://www.google.com"
        assert response.get("valid") is False
        assert response.get("response") is not None
        assert len(response.get("errors")) == 3
        assert response_data.request.headers == {'Content-Length': '21',
                                                 'Content-Type': 'application/x-www-form-urlencoded', 'header': 'a'}
