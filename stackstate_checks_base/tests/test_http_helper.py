import unittest
from requests import Session, Request
from schematics.models import Model
from schematics.types import StringType, IntType, BooleanType
from stackstate_checks.utils.http_helper import HTTPHelper, HTTPRequestType, HTTPAuthenticationType, HTTPResponseType
from requests.auth import HTTPBasicAuth
import requests_mock
import json


class BodySchematicTest(Model):
    title = StringType(required=True)
    body = StringType(required=True)
    userId = IntType(required=True)


class BodyResponseSchematicTest(Model):
    hello = StringType(required=True)
    pong = BooleanType(required=True)


class TestHTTPHelper(unittest.TestCase):
    def test_http_method(self):
        expect_success_methods = ["POST", "GET", "PUT", "PATCH", "DELETE"]
        expect_failure_methods = ["HEAD", "UNKNOWN", "RANDOM"]

        # We are expecting these methods to successfully be applied
        def expect_success(method):
            http_success = HTTPHelper()
            http_success.set_method(method)
            assert http_success.get_method() is method
        map(expect_success, expect_success_methods)

        # We are expecting these methods to fail be applied
        def expect_failure(method):
            http_failure = HTTPHelper()
            http_failure.set_method(method)
            assert http_failure.get_method() is None
        map(expect_failure, expect_failure_methods)

        # We are testing if the method apply overwrites and resets on incorrect or blank
        http = HTTPHelper()
        # Apply GET
        http.set_method("GET")
        assert http.get_method() == "GET"
        # Apply POST
        http.set_method("POST")
        assert http.get_method() == "POST"
        # Apply Invalid Value
        http.set_method("BLANK")
        assert http.get_method() is None
        # Apply GET
        http.set_method("GET")
        assert http.get_method() == "GET"
        # Attempt to reset value
        http.set_method()
        assert http.get_method() is None

    def test_http_url(self):
        endpoint_main = "https://http-handle.free.beeceptor.com/post/200/0/headers/body/json/v1"
        endpoint_main_ip = "http://0.0.0.0:1234"
        endpoint_parameters = ";a=1?b=2#c=3"

        # Test the main endpoint without parameters
        # Endpoint should not change
        http = HTTPHelper()
        http.set_url(endpoint_main)
        assert http.get_url() == endpoint_main
        # Reset the url
        http.set_url()
        assert http.get_url() is None

        # Test the main endpoint with parameters
        # Endpoint should change and not contain parameters
        http = HTTPHelper()
        http.set_url(endpoint_main + endpoint_parameters)
        assert http.get_url() == endpoint_main
        # Reset the url
        http.set_url()
        assert http.get_url() is None

        # Test the main ip endpoint
        # Endpoint should not change
        http = HTTPHelper()
        http.set_url(endpoint_main_ip)
        assert http.get_url() == endpoint_main_ip
        # Reset the url
        http.set_url()
        assert http.get_url() is None

    def test_http_query_parameters(self):
        endpoint_main = "https://http-handle.free.beeceptor.com/post/200/0/headers/body/json/v1"
        endpoint_parameters = ";a=1?b=2#c=3"
        endpoint_parameters_alt = ";ab=1?bc=2#cd=3"

        # URL Affect tests

        # Test the main endpoint without parameters
        http = HTTPHelper()
        http.set_url(endpoint_main)
        assert http.get_query_parameters() == {}

        # Not Session Wide
        http = HTTPHelper()
        http.set_url(endpoint_main + endpoint_parameters)
        assert http.get_query_parameters() == {'b': '2'}
        assert http.get_query_parameters(True) == {}

        # Not Session Wide + Changes
        http = HTTPHelper()
        http.set_url(endpoint_main + endpoint_parameters)
        assert http.get_query_parameters() == {'b': '2'}
        assert http.get_query_parameters(True) == {}
        http.set_url(endpoint_main + endpoint_parameters_alt)
        assert http.get_query_parameters() == {'bc': '2'}
        assert http.get_query_parameters(True) == {}

        # Is Session Wide
        http = HTTPHelper()
        http.set_url(endpoint_main + endpoint_parameters, True)
        assert http.get_query_parameters() == {}
        assert http.get_query_parameters(True) == {'b': '2'}

        # Is Session Wide + Changes
        http = HTTPHelper()
        http.set_url(endpoint_main + endpoint_parameters, True)
        assert http.get_query_parameters() == {}
        assert http.get_query_parameters(True) == {'b': '2'}
        http.set_url(endpoint_main + endpoint_parameters_alt, True)
        assert http.get_query_parameters() == {}
        assert http.get_query_parameters(True) == {'b': '2', 'bc': '2'}

        # Direct apply test

        # Reset
        http = HTTPHelper()
        http.set_query_parameters()
        assert http.get_query_parameters() == {}

        # Empty String
        http = HTTPHelper()
        http.set_query_parameters("")
        assert http.get_query_parameters() == {}

        # Random String
        http = HTTPHelper()
        http.set_query_parameters("this is some random text")
        assert http.get_query_parameters() == {}

        # 1 Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world")
        assert http.get_query_parameters() == {'hello': 'world'}

        # 5 Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world&test=123&around=world&single=ahoy&qwerty=test")
        assert http.get_query_parameters() == {
            'hello': 'world',
            'test': '123',
            'around': 'world',
            'single': 'ahoy',
            'qwerty': 'test'
        }

        # Same Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world&hello=test&hello=end")
        assert http.get_query_parameters() == {'hello': 'end'}

        # Session - Reset
        http = HTTPHelper()
        http.set_query_parameters(None, True)
        assert http.get_query_parameters(True) == {}

        # Session - Empty String
        http = HTTPHelper()
        http.set_query_parameters("", True)
        assert http.get_query_parameters(True) == {}

        # Session - Random String
        http = HTTPHelper()
        http.set_query_parameters("this is some random text", True)
        assert http.get_query_parameters(True) == {}

        # Session - 1 Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world", True)
        assert http.get_query_parameters(True) == {'hello': 'world'}

        # Session - 5 Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world&test=123&around=world&single=ahoy&qwerty=test", True)
        assert http.get_query_parameters(True) == {
            'hello': 'world',
            'test': '123',
            'around': 'world',
            'single': 'ahoy',
            'qwerty': 'test'
        }

        # Session - Same Parameter test
        http = HTTPHelper()
        http.set_query_parameters("hello=world&hello=test&hello=end", True)
        assert http.get_query_parameters(True) == {'hello': 'end'}

        # Session - Keep query parameters
        http = HTTPHelper()
        http.set_query_parameters("hello=world", True)
        assert http.get_query_parameters(True) == {'hello': 'world'}
        http.set_query_parameters("test=123", True)
        assert http.get_query_parameters(True) == {'hello': 'world', 'test': '123'}
        http.set_query_parameters("qwerty=kwerk", True)
        assert http.get_query_parameters(True) == {'hello': 'world', 'test': '123', 'qwerty': 'kwerk'}

    def test_http_body(self):
        body = {'title': 'foo', 'body': 'bar', 'userId': 1}
        body_alt = {'title': 'foo'}

        # Inferred body type
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body)
        assert http.get_body() == body

        # Unsupported body type test
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body("Random Text")
        assert http.get_body() == []

        # Body + Defined JSON Type
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, HTTPRequestType.JSON)
        assert http.get_body() == body

        # Random Type
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, "RANDOM-TYPE")
        assert http.get_body() == []

        # Correct Body + defined schematic
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, HTTPRequestType.JSON, BodySchematicTest)
        assert http.get_body() == body

        # Incorrect Body + defined schematic
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body_alt, HTTPRequestType.JSON, BodySchematicTest)
        assert http.get_body() == []

        # Clear Body
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body_alt, HTTPRequestType.JSON, BodySchematicTest)
        http.set_body()
        assert http.get_body() == []

        # Force method to be set first
        http = HTTPHelper()
        http.set_body(body)
        assert http.get_body() == []

        # Test method that does not require a body
        http = HTTPHelper()
        http.set_method("GET")
        http.set_body(body)
        assert http.get_body() == []

    def test_http_headers(self):
        headers = {'hello': 'world'}
        headers_alt = {'test': '123'}
        session_default_headers = {'User-Agent': 'python-requests/2.24.0',
                                   'Accept-Encoding': 'gzip, deflate',
                                   'Accept': '*/*',
                                   'Connection': 'keep-alive'}

        # Clear headers
        http = HTTPHelper()
        http.set_headers(headers)
        http.set_headers()
        assert http.get_headers() == {}
        assert http.get_headers(True) == session_default_headers

        # Request headers
        http = HTTPHelper()
        http.set_headers(headers)
        assert http.get_headers() == headers
        assert http.get_headers(True) == session_default_headers

        # Session headers
        http = HTTPHelper()
        http.set_headers(headers, True)
        new_headers = session_default_headers.copy()
        new_headers.update(headers)
        assert http.get_headers() == {}
        assert http.get_headers(True) == new_headers

        # Session headers - Persist
        http.set_headers(headers_alt, True)
        new_headers.update(headers_alt)
        assert http.get_headers() == {}
        assert http.get_headers(True) == new_headers

    def test_http_auth(self):
        # Default no auth
        http = HTTPHelper()
        assert http.get_auth() is None
        assert http.get_auth(True) is None

        # Fet auth to blank
        http = HTTPHelper()
        http.set_auth(HTTPAuthenticationType.NoAuth)
        assert http.get_auth() is None
        assert http.get_auth(True) is None
        http.set_auth()
        assert http.get_auth() is None
        assert http.get_auth(True) is None

        # Set request level auth with incorrect details
        http = HTTPHelper()
        http.set_auth(HTTPAuthenticationType.BasicAuth, {
            'test': '123'
        })
        assert http.get_auth() is None

        # TODO:

        #  # Set request level auth with correct details
        #  http = HTTPHelper()
        #  request = Request()
        #  request.auth = HTTPBasicAuth('root', 'root')
        #  http.set_auth(HTTPAuthenticationType.BasicAuth, {
        #      'username': 'root',
        #      'password': 'root'
        #  })
        #  assert http.get_auth().username is request.auth.username
        #  assert http.get_auth().password is request.auth.password

        #  # Set session level auth with correct details
        #  http = HTTPHelper()
        #  session = Session()
        #  session.auth = HTTPBasicAuth('root', 'root')
        #  http.set_auth(HTTPAuthenticationType.BasicAuth, {
        #      'username': 'root',
        #      'password': 'root'
        #  }, True)
        #  assert http.get_auth(True).username is session.auth.username
        #  assert http.get_auth(True).password is session.auth.password

    def test_http_proxy(self):
        proxy_list = {
            "http": "http://10.10.1.10:3128",
            "https": "https://10.10.1.11:1080",
        }
        proxy_list_alt = {
            "ftp": "ftp://10.10.1.10:3128",
        }

        # Default proxy
        http = HTTPHelper()
        assert http.get_proxy() == {}

        # Set proxy
        http = HTTPHelper()
        http.set_proxy(proxy_list)
        assert http.get_proxy() == proxy_list

        # Test proxy session data combine
        http = HTTPHelper()
        http.set_proxy(proxy_list)
        http.set_proxy(proxy_list_alt)
        proxies = proxy_list.copy()
        proxies.update(proxy_list_alt)
        assert http.get_proxy() == proxies

    def test_http_timeout(self):
        # Default timeout
        http = HTTPHelper()
        assert http.get_timeout() is None

        # Set timeout
        http = HTTPHelper()
        http.set_timeout(10)
        assert http.get_timeout() == 10

        # Set timeout then clear it
        http = HTTPHelper()
        http.set_timeout(10)
        http.set_timeout()
        assert http.get_timeout() is None

    def test_http_send(self):
        def mock(method, url, **kwargs):
            http = HTTPHelper()
            adapter = requests_mock.Adapter()
            http.mount_adapter(adapter)
            adapter.register_uri(method, url, **kwargs)
            return http

        # Base Settings
        body = {
            'hello': 'world',
            'test': '123',
        }

        headers = {
            "X-Custom-Header": "custom",
            "Content-Type": "application/json",
            "Content-Length": '20'
        }

        query = {
            "query-a": "hello",
            "query-b": "world"
        }

        """
            Formulate a request:
                - Method: POST
                - Endpoint: mock://test.com
                - Body: true
                - Headers: true
                - Query Params: true
            Expect:
                - Status Code: 200
                - JSON Response
                - No response validation
            ** SUCCESS TEST **
        """
        req = mock("POST", "mock://test.com", json=dict({'hello': 'world', 'pong': True}), status_code=200)
        req.set_url("mock://test.com")
        req.set_method("POST")
        req.set_body(body)
        req.set_headers(headers)
        req.set_query_parameters(query)
        req.set_resp_validation()
        response = req.send()

        assert response.request.url == "mock://test.com"
        assert response.request.body == "hello=world&test=123"
        assert response.request.method == "POST"
        assert response.request.headers == headers
        assert response.status_code == 200
        assert response.content.decode('UTF-8') == json.dumps(dict({'hello': 'world', 'pong': True}))

        """
            Formulate a request:
                - Method: POST
                - Endpoint: mock://test.com
                - Body: true
                - Headers: true
                - Query Params: true
            Expect:
                - Status Code: 200
                - JSON Response
                - Response Validation
            ** SUCCESS TEST **
        """
        req = mock("POST", "mock://test.com", json=dict({'hello': 'world', 'pong': True}), status_code=200)
        req.set_url("mock://test.com")
        req.set_method("POST")
        req.set_body(body)
        req.set_headers(headers)
        req.set_query_parameters(query)
        req.set_resp_validation(HTTPResponseType.JSON, BodyResponseSchematicTest, 200)
        response = req.send()

        assert response.request.url == "mock://test.com"
        assert response.request.body == "hello=world&test=123"
        assert response.request.method == "POST"
        assert response.request.headers == headers
        assert response.status_code == 200
        assert response.content.decode('UTF-8') == json.dumps(dict({'hello': 'world', 'pong': True}))

        """
            Formulate a request:
                - Method: POST
                - Endpoint: mock://test.com
                - Body: true
                - Headers: true
                - Query Params: true
            Expect:
                - Status Code: 200
                - JSON Response
                - Response Validation
                
            ** FAILURE TEST **
                Schematic mismatch from response
        """
        req = mock("POST", "mock://test.com", json=dict({'hello': 'world', 'random': True}), status_code=200)
        req.set_url("mock://test.com")
        req.set_method("POST")
        req.set_body(body)
        req.set_headers(headers)
        req.set_query_parameters(query)
        req.set_resp_validation(HTTPResponseType.JSON, BodyResponseSchematicTest, 200)
        response = req.send()

        assert response is None

        """
            Formulate a request:
                - Method: POST
                - Endpoint: mock://test.com
                - Body: true
                - Headers: true
                - Query Params: true
            Expect:
                - Status Code: 200
                - JSON Response
                - Response Validation
            ** SUCCESS TEST **
        """
        req = mock("POST", "mock://test.com", json=dict({'hello': 'world', 'pong': True}), status_code=404)
        req.set_url("mock://test.com")
        req.set_method("POST")
        req.set_body(body)
        req.set_headers(headers)
        req.set_query_parameters(query)
        req.set_resp_validation(HTTPResponseType.JSON, BodyResponseSchematicTest)
        response = req.send()

        assert response.request.url == "mock://test.com"
        assert response.request.body == "hello=world&test=123"
        assert response.request.method == "POST"
        assert response.request.headers == headers
        assert response.status_code == 404
        assert response.content.decode('UTF-8') == json.dumps(dict({'hello': 'world', 'pong': True}))

