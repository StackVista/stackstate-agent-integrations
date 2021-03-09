import json
import requests_mock
from enum import Enum
from schematics.models import Model
from schematics.types import StringType, URLType, DictType, BooleanType, IntType
from schematics.exceptions import ValidationError, DataError
from requests import Session, Request
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import six

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

"""
    ENUM
        Used to structure the http request
"""


class HTTPMethodEnum(Enum):
    GET = ({
        'type': 'GET',
        'body': False
    })
    POST = ({
        'type': 'POST',
        'body': True
    })
    PUT = ({
        'type': 'PUT',
        'body': True
    })
    PATCH = ({
        'type': 'PATCH',
        'body': True
    })
    DELETE = ({
        'type': 'DELETE',
        'body': False
    })


"""
    Authentication Models
"""


class _HTTPBasicAuth(Model):
    username = StringType(required=True)
    password = StringType(required=True)


"""
    Authentication ENUM
"""


class HTTPAuthenticationType(Enum):
    NoAuth = None
    BasicAuth = _HTTPBasicAuth


"""
    Possible Request and Response objects
"""


class HTTPRequestType(Enum):
    JSON = dict


class HTTPResponseType(Enum):
    PLAIN = str
    JSON = dict


class HTTPHelper:
    # Primary request objects
    session = Session()
    request_object = Request()

    # Extra enums to arrays to find values
    available_method_enums = [item.value for item in HTTPMethodEnum]
    available_method_types = [item.value['type'] for item in HTTPMethodEnum]
    available_request_types = [item.value for item in HTTPRequestType]
    available_authentication_types = [item.value for item in HTTPAuthenticationType]
    available_response_types = [item for item in HTTPResponseType]

    # State of the timeout and retry stats
    timeout = None
    retry_strategy = None
    session_focus = False

    # Init: Reset objects
    def __init__(self, session=False):
        self.session = Session()
        self.request_object = Request()
        self.session_focus = session

    # Reset the session and request objects
    def renew(self):
        self.session = Session()
        self.request_object = Request()

    # Print Errors
    def handle_error(self, error):
        raise Exception(error)

    """
        You can set the type of request through this function for example GET or POST
        The function accepts both string or enum `HTTPMethodEnum` values

        @http_method
            str or method from the HTTPMethodEnum` enum

        ** Affects: Request Object **
    """
    def set_method(self, http_method=None):
        # If the method is blank then we clear the value
        if http_method is None:
            self.request_object.method = None

        # If the supplied method already exists in the enum
        elif http_method in self.available_method_enums:
            self.request_object.method = http_method.value['type']

        # This is a second test to attempt and find the method str inside the enum
        elif http_method in self.available_method_types:
            method_type_index = self.available_method_types.index(http_method)
            if method_type_index > -1 and self.available_method_enums[method_type_index]:
                self.request_object.method = self.available_method_enums[method_type_index]['type']

        # If neither the enum or string could satisfy the request then we see it as a error
        # We also reset the method to none as a invalid type was passed
        else:
            self.request_object.method = None
            self.handle_error(
                "HTTP Method `%s` is not supported, Please use any of the following methods %s" %
                (http_method, ", ".join(self.available_method_types))
            )

    """
        Returns the current state of the supplied method
        ** Affects: None **
    """
    def get_method(self):
        return self.request_object.method

    """
        The target endpoint is applied here, This will be the endpoint hit as soon as the request is made.
        We also attempt to analyze the url and split out any extra data like query parameters etc and
        apply them to the correct locations thus allowing a custom url to affect the requests object.

        @http_url
            The URL endpoint the request will attempt to retrieve information from

        ** Affects: Request Object **
    """
    def set_url(self, http_url=None, session=False):
        session = self.session_focus if session is False else session
        # Reset the URL
        if http_url is None:
            self.request_object.url = None

        elif isinstance(http_url, str):
            # We attempt to parse the url to determine if there is any other parts within the URL
            parsed_url = urlparse.urlparse(http_url)

            # The URL gets reconstructed here and applied
            url = (parsed_url.scheme + "://" if len(parsed_url.scheme) > 0 else "") \
                + parsed_url.netloc \
                + parsed_url.path
            self.request_object.url = url

            # If there was any extra query parameters then we attempt to process it
            if len(parsed_url.query) > 0:
                self.set_query_parameters(parsed_url.query, session)

        # Invalid URL, Reset to none if invalid
        else:
            self.request_object.url = None
            self.handle_error("Invalid URL specified")

    """
        Returns the current state of the supplied url target
        ** Affects: None **
    """
    def get_url(self):
        return self.request_object.url

    """
        Apply query parameters to the request object or session object from either a string that is converted
        to a dict or a straight dict

        @parameters
            Can be a string containing a query string for example test=123&hello=world or this can be a already
            parsed dict
        @session
            If this is true then the session object will be used instead of the requests object

        ** Affects: Session and Request Object **
    """
    def set_query_parameters(self, parameters=None, session=False):
        session = self.session_focus if session is False else session
        _parameters = parameters

        # Clear query parameters
        if parameters is None and session is False:
            self.request_object.params = {}
            return

        elif parameters is None and session is True:
            self.session.params.clear()
            return

        # If the supplied query params is a string, We then attempt to parse it into a dict
        elif isinstance(parameters, str):
            _parameters = self._split_string_into_dict(parameters, "&", "=")

        # Apply to the session object
        if isinstance(_parameters, dict) and session is True:
            self.session.params.update(_parameters)

        # Apply to the request object
        elif isinstance(_parameters, dict) and session is False:
            self.request_object.params = _parameters

        else:
            # Clear query parameters
            if session is False:
                self.request_object.params = {}
            elif session is True:
                self.session.params.clear()

            self.handle_error("Invalid query parameters specified")

    """
        Returns the current state of the query parameters
        ** Affects: None **
    """
    def get_query_parameters(self, session=False):
        session = self.session_focus if session is False else session
        if session is True:
            return self.session.params
        else:
            return self.request_object.params

    """
    """
    @staticmethod
    def _split_string_into_dict(target, delimiter, sub_delimiter):
        if isinstance(target, str):
            items = (item.split(sub_delimiter) for item in target.split(delimiter))
            try:
                return dict((left.strip(), right.strip()) for left, right in items)
            except ValueError:
                return {}
        return None

    """
        Apply a body to the request object. The body will be tested against a type or the type will be inferred if
        possible.
        The body can also be tested against a schematic to prevent requesting with a malformed body

        @body
            Dict object containing a body to be send with the request
        @request_type
            This is the body type defined from the `HTTPRequestType` enum for example HTTPRequestType.JSON
        @mapping_model
            You can supply a schematic model, This model will be used to test against the body

        ** Affects: Request Object **
    """
    def set_body(self, body=None, request_type=None, mapping_model=None):
        # Get the request method
        request_method = HTTPMethodEnum[self.request_object.method] \
            if self.request_object.method in self.available_method_types else None

        # Use the request method to determine if this request requires a body
        if request_method is not None and request_method.value:
            if request_method.value["body"] is not True:
                self.request_object.data = []
                return
        elif self.request_object.method is not None:
            self.handle_error("Invalid request method")
            self.request_object.data = []
            return

        # Clear body
        if body is None:
            self.request_object.data = []

        # Infer that the type is json
        elif body is not None \
                and isinstance(body, dict) \
                and request_type is None \
                and mapping_model is None:
            self.request_object.data = body

        # Test if the defined type is the same as the value without a model
        elif body is not None \
                and isinstance(request_type, Enum) \
                and isinstance(body, request_type.value) \
                and mapping_model is None:
            self.request_object.data = body

        # Test if the defined type is the same as the value with a model
        elif body is not None \
                and isinstance(request_type, Enum) \
                and isinstance(body, request_type.value) \
                and mapping_model is not None:
            try:
                mapping_model(body).validate()
                self.request_object.data = body
            except DataError:
                self.handle_error("Invalid body, Does not match schematic")
                self.request_object.data = []

    """
        Returns the current state of the body
        ** Affects: None **
    """
    def get_body(self):
        if self.request_object.data is None or len(self.request_object.data) == 0:
            return None
        return self.request_object.data

    """
        Apply a dict to the active request object or session object

        @headers
            A dict containing all the header key value pairs
        @session
            If this is true then the session object will be used instead of the requests object
    """
    def set_headers(self, headers=None, session=False):
        session = self.session_focus if session is False else session

        # Apply to the session
        if isinstance(headers, dict) and session is True:
            self.session.headers.update(headers)
        # Apply to the request object
        elif isinstance(headers, dict):
            self.request_object.headers = headers
        # Wipe the variable
        else:
            self.request_object.headers = {}

    """
        Returns the current state of the headers
        ** Affects: None **
    """
    def get_headers(self, session=False):
        session = self.session_focus if session is False else session
        if session:
            return self.session.headers
        else:
            return self.request_object.headers

    """
        Set authentication on the http request. The authentication details is validated against a schematic

        @schematic
            This is the HTTP Enum that is used to test the details passed down
        @details
            A dict of the credentials required in the 'schematic' enum
        @session
            Should this be applied on the session on request
    """
    def set_auth(self, schematic=None, details=None, session=False):
        session = self.session_focus if session is False else session
        # Reset session auth
        if (schematic is None or schematic.value is HTTPAuthenticationType.NoAuth or schematic.value is None) \
                and session is True:
            self.session.auth = None

        # Reset request object auth
        elif (schematic is None or schematic.value is HTTPAuthenticationType.NoAuth or schematic.value is None) \
                and session is False:
            self.request_object.auth = None

        # If the auth method and data is valid
        elif schematic is not None and \
                schematic.value in self.available_authentication_types and \
                isinstance(details, dict):
            try:
                # Validate data
                data = schematic.value(details)
                data.validate()

                # Apply session data
                if schematic is HTTPAuthenticationType.BasicAuth and session is True:
                    self.session.auth = HTTPBasicAuth(data.username, data.password)

                # Apply request data
                elif schematic is HTTPAuthenticationType.BasicAuth and session is False:
                    self.request_object.auth = HTTPBasicAuth(data.username, data.password)

            # If validation failed
            except DataError:
                self.handle_error("Auth details does not match the schematic")
                if session is True:
                    self.session.auth = None
                else:
                    self.request_object.auth = None
        else:
            self.handle_error("Invalid authentication method supplied")

    """
        Returns the current state of the auth
        ** Affects: None **
    """
    def get_auth(self, session=False):
        session = self.session_focus if session is False else session
        if session is True:
            return self.session.auth
        else:
            return self.request_object.auth

    """
        Set a proxy that the request will use

        @proxies
            The proxy object as defined in the requests library
    """
    def set_proxy(self, proxies=None):
        # Reset the proxy
        if proxies is None:
            self.session.proxies.clear()

        # Make sure the proxy is a correct type
        elif isinstance(proxies, dict):
            self.session.proxies.update(proxies)

        # If all fails
        else:
            self.handle_error("Invalid proxy details")

    """
        Returns the current state of the proxy
        ** Affects: None **
    """
    def get_proxy(self):
        return self.session.proxies

    """
        Set current request timeout

        @timeout
            Integer timeout
    """
    def set_timeout(self, timeout=None):
        if isinstance(timeout, int):
            self.timeout = timeout
        else:
            self.timeout = None

    """
        Returns the current state of the proxy
        ** Affects: None **
    """
    def get_timeout(self):
        return self.timeout

    """
        # Validate
        @timeout
    """
    resp_validate_schematic = None
    resp_validate_status_code = None
    resp_validate_strict_type = None

    def set_resp_validation(self, strict_type=None, schematic=None, status_code=None):
        self.resp_validate_schematic = schematic
        self.resp_validate_status_code = status_code
        if strict_type in self.available_response_types:
            self.resp_validate_strict_type = strict_type

    """
        Returns the current state of the validations
        ** Affects: None **
    """
    def get_resp_validate_schematic(self):
        return self.resp_validate_schematic

    def get_resp_validate_status_code(self):
        return self.resp_validate_status_code

    def get_resp_validate_strict_type(self):
        return self.resp_validate_strict_type

    """
        Used for unit testing only
    """
    def mount_adapter(self, adapter):
        self.session.mount('mock://', adapter)

    """
        Uses the Retry object from requests allowing the user to apply the same kwargs parameters

        @kwargs
            List items accepted by the Retry function
    """
    def set_retry_policy(self, **kwargs):
        adapter = None

        if len(kwargs) > 0:
            self.retry_strategy = Retry(**kwargs)
            adapter = HTTPAdapter(max_retries=self.retry_strategy)

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    """
        Returns the current state of the retry policy
        ** Affects: None **
    """
    def get_retry_policy(self):
        return self.retry_strategy

    """
        Set the current state of the SSL verification, Set to False so that SSL is not verified

        @verify
            True or False to enable or disable ssl verification
    """
    def set_ssl_verify(self, verify=None):
        if isinstance(verify, bool):
            self.session.verify = verify
        else:
            self.session.verify = True

    """
        Returns the current state of the SSL
        ** Affects: None **
    """
    def get_ssl_verify(self):
        return self.session.verify

    """
        This function is used to send out the request that has been build up
        It has one of two return types
            - The response from the request
            - Or None if the response fails any validations unless no validation was defined and the response is JSON
    """
    def send(self):
        # Send the request out
        response = self.session.send(self.request_object.prepare(),
                                     timeout=self.timeout)

        # If there is a forced status code check
        if self.resp_validate_status_code is not None and response.status_code != self.resp_validate_status_code:
            return None

        # Schematic: Some
        # Strict Type: None or HTTPResponseType.JSON
        # Response.content: Some
        # Inferred Type: JSON
        elif (self.resp_validate_strict_type is None or self.resp_validate_strict_type is HTTPResponseType.JSON) and \
                self.resp_validate_schematic is not None and\
                response.content is not None and \
                len(response.content) > 0:

            # First lets attempt a JSON body
            # If we are able to parse it let's then test the body
            try:
                json_response = json.loads(response.content)
                if self.resp_validate_schematic is not None:
                    self.resp_validate_schematic(json_response).validate()
                return response

            except DataError:
                self.handle_error("Invalid response, Does not match schematic")
                return None

            except Exception:
                self.handle_error("Invalid response, Unable to determine JSON")
                return None

        # Schematic: None
        # Strict Type: HTTPResponseType.PLAIN
        # Response.content: Some
        elif self.resp_validate_strict_type is HTTPResponseType.PLAIN and \
                isinstance(response.content, six.binary_type):
            return response

        # Else lets test if the body has valid JSON
        try:
            json.loads(response.content)
            return response

        except Exception:
            return None

    """
        Compact methods
    """
    @staticmethod
    def _request_builder(method, **kwargs):
        http = HTTPHelper()
        use_session = True if kwargs.get("use_session") is True else False

        if kwargs.get("mock") is True:
            adapter = requests_mock.Adapter()
            http.mount_adapter(adapter)
            adapter.register_uri(method,
                                 kwargs.get("url"),
                                 status_code=kwargs.get("mock_status"),
                                 json=kwargs.get("mock_response"))

        http.set_url(kwargs.get("url"), use_session)
        http.set_method(method)
        http.set_body(
            kwargs.get("body"),
            kwargs.get("body_validate_type"),
            kwargs.get("body_validate_model")
        )
        http.set_timeout(kwargs.get("timeout"))
        http.set_headers(kwargs.get("headers"), use_session)
        http.set_query_parameters(kwargs.get("query"), use_session)
        http.set_resp_validation(kwargs.get("validate_type"),
                                 kwargs.get("validate_schematic"),
                                 kwargs.get("validate_status_code"))
        http.set_ssl_verify(kwargs.get("ssl_verify"))

        if isinstance(kwargs.get("retry_policy"), dict):
            http.set_retry_policy(**kwargs.get("retry_policy"))

        return http

    def get(self, **kwargs):
        http = self._request_builder("GET", **kwargs)
        return http

    def post(self, **kwargs):
        http = self._request_builder("POST", **kwargs)
        return http

    def put(self, **kwargs):
        http = self._request_builder("PUT", **kwargs)
        return http

    def patch(self, **kwargs):
        http = self._request_builder("PATCH", **kwargs)
        return http

    def delete(self, **kwargs):
        http = self._request_builder("DELETE", **kwargs)
        return http
