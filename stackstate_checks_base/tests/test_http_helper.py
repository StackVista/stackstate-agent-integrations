import unittest
import requests_mock
import json
from requests import Session, Request
from schematics.models import Model
from schematics.types import StringType, IntType, BooleanType
from stackstate_checks.utils.http_helper import HTTPHelper, HTTPRequestType, HTTPAuthenticationType, HTTPResponseType
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.util.retry import Retry


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
            try:
                # Incorrect Body + defined schematic
                http_failure = HTTPHelper()
                http_failure.set_method(method)
                assert http == {'test': 'Should never reach this assert as it should have failed'}
            except Exception as msg:
                assert str(msg) == 'HTTP Method `' + method + \
                       '` is not supported, Please use any of the following methods DELETE, GET, PATCH, POST, PUT'

        map(expect_failure, expect_failure_methods)

        # We are testing if the method apply overwrites and resets on incorrect or blank
        http = HTTPHelper()
        # Apply GET
        http.set_method("GET")
        assert http.get_method() == "GET"
        # Apply POST
        http.set_method("POST")
        assert http.get_method() == "POST"
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

    # We test here to see if the top level session set works
    # Session is set to True in the class constructor
    def test_global_session_apply(self):
        headers = {'hello': 'world'}
        session_default_headers = {'User-Agent': 'python-requests/2.24.0',
                                   'Accept-Encoding': 'gzip, deflate',
                                   'Accept': '*/*',
                                   'Connection': 'keep-alive',
                                   'hello': 'world'}

        http = HTTPHelper(True)
        http.set_headers(headers)
        assert http.get_headers() == session_default_headers

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
        assert http.get_body() is None

        # Body + Defined JSON Type
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, HTTPRequestType.JSON)
        assert http.get_body() == body

        # Random Type
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, "RANDOM-TYPE")
        assert http.get_body() is None

        # Correct Body + defined schematic
        http = HTTPHelper()
        http.set_method("POST")
        http.set_body(body, HTTPRequestType.JSON, BodySchematicTest)
        assert http.get_body() == body

        try:
            # Incorrect Body + defined schematic
            http = HTTPHelper()
            http.set_method("POST")
            http.set_body(body_alt, HTTPRequestType.JSON, BodySchematicTest)
            assert http == {'test': 'Should never reach this assert as it should have failed'}
        except Exception as msg:
            assert str(msg) == 'Invalid body, Does not match schematic'

        try:
            # Clear Body
            http = HTTPHelper()
            http.set_method("POST")
            http.set_body(body_alt, HTTPRequestType.JSON, BodySchematicTest)
            http.set_body()
            assert http == {'test': 'Should never reach this assert as it should have failed'}
        except Exception as msg:
            assert str(msg) == 'Invalid body, Does not match schematic'

        # Test method that does not require a body
        http = HTTPHelper()
        http.set_method("GET")
        http.set_body(body)
        assert http.get_body() is None

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

        try:
            # Set request level auth with incorrect details
            http = HTTPHelper()
            http.set_auth(HTTPAuthenticationType.BasicAuth, {
                'test': '123'
            })
            assert http == {'test': 'Should never reach this assert as it should have failed'}
        except Exception as msg:
            assert str(msg) == 'Auth details does not match the schematic'

        # Set request level auth with correct details
        http = HTTPHelper()
        request = Request()
        request.auth = HTTPBasicAuth('root', 'root')
        http.set_auth(HTTPAuthenticationType.BasicAuth, {
            'username': 'root',
            'password': 'root'
        })

        assert http.get_auth().username == request.auth.username
        assert http.get_auth().password == request.auth.password

        # Set session level auth with correct details
        http = HTTPHelper()
        session = Session()
        session.auth = HTTPBasicAuth('root', 'root')
        http.set_auth(HTTPAuthenticationType.BasicAuth, {
            'username': 'root',
            'password': 'root'
        }, True)
        assert http.get_auth(True).username == session.auth.username
        assert http.get_auth(True).password == session.auth.password

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
        assert response.request.body == "hello=world&test=123" or \
               response.request.body == "test=123&hello=world"
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
        assert response.request.body == "hello=world&test=123" or \
               response.request.body == "test=123&hello=world"
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

        try:
            response = req.send()
            assert response == {'test': 'Should never reach this assert as it should have failed'}
        except Exception as msg:
            assert str(msg) == 'Invalid response, Does not match schematic'

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
        assert response.request.body == "hello=world&test=123" or \
               response.request.body == "test=123&hello=world"
        assert response.request.method == "POST"
        assert response.request.headers == headers
        assert response.status_code == 404
        assert response.content.decode('UTF-8') == json.dumps(dict({'hello': 'world', 'pong': True}))

    def test_retry_policy(self):
        http = HTTPHelper()
        http.set_retry_policy(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
            connect=4,
            read=10,
            raise_on_redirect=10,
            redirect=3
        )

        assert http.get_retry_policy().total == 3
        assert http.get_retry_policy().status_forcelist == [429, 500, 502, 503, 504]
        assert http.get_retry_policy().read == 10
        assert http.get_retry_policy().backoff_factor == 1
        assert http.get_retry_policy().connect == 4
        assert http.get_retry_policy().method_whitelist == ["HEAD", "GET", "OPTIONS"]
        assert http.get_retry_policy().raise_on_redirect == 10
        assert http.get_retry_policy().redirect == 3

    def test_ssl_verify(self):
        # Default SSL test
        http = HTTPHelper()
        http.set_ssl_verify()
        assert http.get_ssl_verify() is True

        # Active SSL test
        http = HTTPHelper()
        http.set_ssl_verify(True)
        assert http.get_ssl_verify() is True

        # Inactive SSL test
        http = HTTPHelper()
        http.set_ssl_verify(False)
        assert http.get_ssl_verify() is False

    def test_compact_methods(self):
        # Base Settings
        body = {
            'hello': 'world',
            'test': '123',
        }

        body_response = {
            'hello': 'world',
            'pong': True
        }

        headers = {
            "X-Custom-Header": "custom",
            "Content-Type": "application/json",
            "Content-Length": '20'
        }

        headers_session = {
            'User-Agent': 'python-requests/2.24.0',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'X-Custom-Header': 'custom',
            'Content-Type': 'application/json',
            'Content-Length': '20'
        }

        query = {
            "query-a": "hello",
            "query-b": "world"
        }

        # GET Tests

        get_request = HTTPHelper().get(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=999,
            validate_type=HTTPResponseType.JSON,
            validate_schematic=BodyResponseSchematicTest,
            validate_status_code=999,
            timeout=30,
            headers=headers,
            query=query,
            body=body,
            body_type=HTTPRequestType.JSON,
            body_model=BodySchematicTest,
            use_session=True,
            ssl_verify=True,
            retry_policy=dict(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 504),
            )
        )
        get_response = get_request.send()
        assert get_request.get_url() == "mock://test.com"
        assert get_request.get_method() == "GET"
        assert get_request.get_body() is None
        assert get_request.get_timeout() == 30
        assert get_request.get_headers(True) == headers_session
        assert get_request.get_ssl_verify() is True
        assert get_request.get_query_parameters(True) == query
        assert get_request.get_proxy() == {}
        assert get_request.get_resp_validate_schematic() == BodyResponseSchematicTest
        assert get_request.get_resp_validate_status_code() == 999
        assert get_request.get_resp_validate_strict_type() == HTTPResponseType.JSON
        assert get_request.get_query_parameters(True) == query
        assert get_response.request.url == "mock://test.com"
        assert get_response.request.method == "GET"
        assert get_response.request.body is None
        assert get_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert get_response.status_code == 999

        get_request = HTTPHelper().get(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
        )
        # awe
        get_response = get_request.send()
        assert get_request.get_url() == "mock://test.com"
        assert get_request.get_method() == "GET"
        assert get_request.get_body() is None
        assert get_request.get_timeout() is None
        assert get_request.get_headers(True) == {'User-Agent': 'python-requests/2.24.0',
                                                 'Accept-Encoding': 'gzip, deflate',
                                                 'Accept': '*/*',
                                                 'Connection': 'keep-alive'}
        assert get_request.get_ssl_verify() is True
        assert get_request.get_query_parameters(True) == {}
        assert get_request.get_query_parameters() == {}
        assert get_request.get_proxy() == {}
        assert get_request.get_resp_validate_schematic() is None
        assert get_request.get_resp_validate_status_code() is None
        assert get_request.get_resp_validate_strict_type() is None
        assert get_response.request.url == "mock://test.com"
        assert get_response.request.method == "GET"
        assert get_response.request.body is None
        assert get_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert get_response.status_code == 200
        assert get_request.get_query_parameters(True) == {}
        assert get_request.get_query_parameters() == {}

        # POST Tests

        post_request = HTTPHelper().post(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=805,
            validate_type=HTTPResponseType.JSON,
            validate_schematic=BodyResponseSchematicTest,
            validate_status_code=805,
            timeout=30,
            headers=headers,
            query=query,
            body=body,
            body_type=HTTPRequestType.JSON,
            body_model=BodySchematicTest,
            use_session=True,
            ssl_verify=True,
            retry_policy=dict(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 504),
            )
        )
        post_response = post_request.send()
        assert post_request.get_url() == "mock://test.com"
        assert post_request.get_method() == "POST"
        assert post_request.get_timeout() == 30
        assert post_request.get_headers(True) == headers_session
        assert post_request.get_ssl_verify() is True
        assert post_request.get_query_parameters(True) == query
        assert post_request.get_proxy() == {}
        assert post_request.get_resp_validate_schematic() == BodyResponseSchematicTest
        assert post_request.get_resp_validate_status_code() == 805
        assert post_request.get_resp_validate_strict_type() == HTTPResponseType.JSON
        assert post_response.request.url == "mock://test.com"
        assert post_response.request.method == "POST"
        assert post_response.request.body == "hello=world&test=123" or \
               post_response.request.body == "test=123&hello=world"
        assert post_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert post_response.status_code == 805
        assert post_request.get_query_parameters(True) == query

        post_request = HTTPHelper().post(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
        )
        post_response = post_request.send()
        assert post_request.get_url() == "mock://test.com"
        assert post_request.get_method() == "POST"
        assert post_request.get_body() is None
        assert post_request.get_timeout() is None
        assert post_request.get_headers(True) == {'User-Agent': 'python-requests/2.24.0',
                                                  'Accept-Encoding': 'gzip, deflate',
                                                  'Accept': '*/*',
                                                  'Connection': 'keep-alive'}
        assert post_request.get_ssl_verify() is True
        assert post_request.get_query_parameters(True) == {}
        assert post_request.get_query_parameters() == {}
        assert post_request.get_proxy() == {}
        assert post_request.get_resp_validate_schematic() is None
        assert post_request.get_resp_validate_status_code() is None
        assert post_request.get_resp_validate_strict_type() is None
        assert post_response.request.url == "mock://test.com"
        assert post_response.request.method == "POST"
        assert post_response.request.body is None
        assert post_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert post_response.status_code == 200
        assert post_request.get_query_parameters(True) == {}
        assert post_request.get_query_parameters() == {}

        # PUT Tests

        put_request = HTTPHelper().put(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
            validate_type=HTTPResponseType.JSON,
            validate_schematic=BodyResponseSchematicTest,
            validate_status_code=200,
            timeout=30,
            headers=headers,
            query=query,
            body=body,
            body_type=HTTPRequestType.JSON,
            body_model=BodySchematicTest,
            use_session=True,
            ssl_verify=True,
            retry_policy=dict(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 504),
            )
        )

        put_response = put_request.send()
        assert put_request.get_url() == "mock://test.com"
        assert put_request.get_method() == "PUT"
        assert put_request.get_body() == body
        assert put_request.get_timeout() == 30
        assert put_request.get_headers(True) == headers_session
        assert put_request.get_ssl_verify() is True
        assert put_request.get_query_parameters(True) == query
        assert put_request.get_proxy() == {}
        assert put_request.get_resp_validate_schematic() == BodyResponseSchematicTest
        assert put_request.get_resp_validate_status_code() == 200
        assert put_request.get_resp_validate_strict_type() == HTTPResponseType.JSON
        assert put_response.request.url == "mock://test.com"
        assert put_response.request.method == "PUT"
        assert put_response.request.body == "hello=world&test=123" or \
               put_response.request.body == "test=123&hello=world"
        assert put_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert put_response.status_code == 200
        assert put_request.get_query_parameters(True) == query

        put_request = HTTPHelper().put(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
        )
        put_response = put_request.send()
        assert put_request.get_url() == "mock://test.com"
        assert put_request.get_method() == "PUT"
        assert put_request.get_body() is None
        assert put_request.get_timeout() is None
        assert put_request.get_headers(True) == {'User-Agent': 'python-requests/2.24.0',
                                                 'Accept-Encoding': 'gzip, deflate',
                                                 'Accept': '*/*',
                                                 'Connection': 'keep-alive'}
        assert put_request.get_ssl_verify() is True
        assert put_request.get_query_parameters(True) == {}
        assert put_request.get_query_parameters() == {}
        assert put_request.get_proxy() == {}
        assert put_request.get_resp_validate_schematic() is None
        assert put_request.get_resp_validate_status_code() is None
        assert put_request.get_resp_validate_strict_type() is None
        assert put_response.request.url == "mock://test.com"
        assert put_response.request.method == "PUT"
        assert put_response.request.body is None
        assert put_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert put_response.status_code == 200
        assert put_request.get_query_parameters(True) == {}
        assert put_request.get_query_parameters() == {}

        # PATCH Tests

        patch_request = HTTPHelper().patch(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
            validate_type=HTTPResponseType.JSON,
            validate_schematic=BodyResponseSchematicTest,
            validate_status_code=200,
            timeout=30,
            headers=headers,
            query=query,
            body=body,
            body_type=HTTPRequestType.JSON,
            body_model=BodySchematicTest,
            use_session=True,
            ssl_verify=True,
            retry_policy=dict(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 504),
            )
        )
        patch_response = patch_request.send()
        assert patch_request.get_url() == "mock://test.com"
        assert patch_request.get_method() == "PATCH"
        assert patch_request.get_body() is body
        assert patch_request.get_timeout() == 30
        assert patch_request.get_headers(True) == headers_session
        assert patch_request.get_ssl_verify() is True
        assert patch_request.get_query_parameters(True) == query
        assert patch_request.get_proxy() == {}
        assert patch_request.get_resp_validate_schematic() == BodyResponseSchematicTest
        assert patch_request.get_resp_validate_status_code() == 200
        assert patch_request.get_resp_validate_strict_type() == HTTPResponseType.JSON
        assert patch_response.request.url == "mock://test.com"
        assert patch_response.request.method == "PATCH"
        assert patch_response.request.body == "hello=world&test=123" or \
               patch_response.request.body == "test=123&hello=world"
        assert patch_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert patch_response.status_code == 200
        assert patch_request.get_query_parameters(True) == query

        patch_request = HTTPHelper().patch(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
        )
        patch_response = patch_request.send()
        assert patch_request.get_url() == "mock://test.com"
        assert patch_request.get_method() == "PATCH"
        assert patch_request.get_body() is None
        assert patch_request.get_timeout() is None
        assert patch_request.get_headers(True) == {'User-Agent': 'python-requests/2.24.0',
                                                   'Accept-Encoding': 'gzip, deflate',
                                                   'Accept': '*/*',
                                                   'Connection': 'keep-alive'}
        assert patch_request.get_ssl_verify() is True
        assert patch_request.get_query_parameters(True) == {}
        assert patch_request.get_query_parameters() == {}
        assert patch_request.get_proxy() == {}
        assert patch_request.get_resp_validate_schematic() is None
        assert patch_request.get_resp_validate_status_code() is None
        assert patch_request.get_resp_validate_strict_type() is None
        assert patch_response.request.url == "mock://test.com"
        assert patch_response.request.method == "PATCH"
        assert patch_response.request.body is None
        assert patch_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert patch_response.status_code == 200
        assert patch_request.get_query_parameters(True) == {}
        assert patch_request.get_query_parameters() == {}

        # DELETE Tests

        delete_request = HTTPHelper().delete(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
            validate_type=HTTPResponseType.JSON,
            validate_schematic=BodyResponseSchematicTest,
            validate_status_code=200,
            timeout=30,
            headers=headers,
            query=query,
            body=body,
            body_validate_type=HTTPRequestType.JSON,
            body_validate_model=BodySchematicTest,
            use_session=True,
            ssl_verify=True,
            retry_policy=dict(
                total=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 504),
            )
        )
        delete_response = delete_request.send()
        assert delete_request.get_url() == "mock://test.com"
        assert delete_request.get_method() == "DELETE"
        assert delete_request.get_body() is None
        assert delete_request.get_timeout() == 30
        assert delete_request.get_headers(True) == headers_session
        assert delete_request.get_ssl_verify() is True
        assert delete_request.get_query_parameters(True) == query
        assert delete_request.get_proxy() == {}
        assert delete_request.get_resp_validate_schematic() == BodyResponseSchematicTest
        assert delete_request.get_resp_validate_status_code() == 200
        assert delete_request.get_resp_validate_strict_type() == HTTPResponseType.JSON
        assert delete_response.request.url == "mock://test.com"
        assert delete_response.request.method == "DELETE"
        assert delete_response.request.body is None
        assert delete_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert delete_response.status_code == 200
        assert delete_request.get_query_parameters(True) == query

        delete_request = HTTPHelper().delete(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=200,
        )
        delete_response = delete_request.send()
        assert delete_request.get_url() == "mock://test.com"
        assert delete_request.get_method() == "DELETE"
        assert delete_request.get_body() is None
        assert delete_request.get_timeout() is None
        assert delete_request.get_headers(True) == {'User-Agent': 'python-requests/2.24.0',
                                                    'Accept-Encoding': 'gzip, deflate',
                                                    'Accept': '*/*',
                                                    'Connection': 'keep-alive'}
        assert delete_request.get_ssl_verify() is True
        assert delete_request.get_query_parameters(True) == {}
        assert delete_request.get_query_parameters() == {}
        assert delete_request.get_proxy() == {}
        assert delete_request.get_resp_validate_schematic() is None
        assert delete_request.get_resp_validate_status_code() is None
        assert delete_request.get_resp_validate_strict_type() is None
        assert delete_response.request.url == "mock://test.com"
        assert delete_response.request.method == "DELETE"
        assert delete_response.request.body is None
        assert delete_response.content.decode('UTF-8') == json.dumps(dict(body_response))
        assert delete_response.status_code == 200
        assert delete_request.get_query_parameters(True) == {}
        assert delete_request.get_query_parameters() == {}

    def test_unique_events(self):
        body_response = {
            'hello': 'world',
            'pong': True
        }

        # Testing a 400 Response
        # The body still has data al tho the server responded with a 400 meaning we might still want to see the data
        post_response = HTTPHelper().post(
            url="mock://test.com",
            mock=True,
            mock_response=dict(body_response),
            mock_status=400,
        ).send()

        assert post_response is not None
        assert post_response.content.decode('UTF-8') == json.dumps(dict(body_response))

        # Testing a 200 Response
        # The server responded with a 200 but the body is still not found
        post_response = HTTPHelper().post(
            url="mock://test.com",
            mock=True,
            mock_status=200,
        ).send()

        assert post_response is None
