from requests import Session, Request
import requests_mock
import json
from enum import Enum
from schematics.models import Model
from schematics.types import StringType, URLType, DictType, BooleanType, IntType
from schematics.exceptions import ValidationError, DataError
from requests.auth import HTTPBasicAuth

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class _HTTPMethodEnum(Model):
    type = StringType(required=True)
    body = BooleanType(required=True)


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


class RequestStructure(Model):
    http_method = StringType(required=True, choices=[item.value["type"] for item in HTTPMethodEnum])
    http_url = StringType(required=True)
    http_body = DictType(StringType, default=None)

    def validate_http_body(self, data, value):
        # Formulate a list of all the available methods
        available_methods = [item.value for item in HTTPMethodEnum]

        print(data['http_method'])

        # Find the matching method to test if we require a body
        find_method = list(filter(lambda method: method['type'] == data['http_method'], available_methods))
        if len(find_method) > 0 and 'body' in find_method[0]:

            if find_method[0]['body'] is False and data['http_body'] is not None:
                print("Body will not be send")
            elif find_method[0]['body'] is True and data['http_body'] is None:
                print("Body required")
        else:
            print("Method not found error")

        return value


class _HTTPBasicAuth(Model):
    username = StringType(required=True)
    password = StringType(required=True)


class HTTPAuthenticationType(Enum):
    NoAuth = None
    BasicAuth = _HTTPBasicAuth


class HTTPRequestType(Enum):
    JSON = dict


class HTTPResponseTypes(Enum):
    TEXT = 'TEXT'
    JSON = 'JSON'
    XML = 'XML'


class BodySchematicTest(Model):
    title = StringType(required=True)
    body = StringType(required=True)
    userId = IntType(required=True)


class HTTPHelper:
    session = Session()
    request_object = Request()
    error_alternative = None
    request_method_enum_list = [item.value['type'] for item in HTTPMethodEnum]
    available_method_enums = [item.value for item in HTTPMethodEnum]
    available_method_types = [item.value['type'] for item in HTTPMethodEnum]
    available_request_types = [item.value for item in HTTPRequestType]
    available_authentication_types = [item.value for item in HTTPAuthenticationType]
    timeout = None

    def __init__(self):
        self.renew_session()

    def renew_session(self):
        self.session = Session()
        self.request_object = Request()

    def handle_error(self, error):
        print(error)
        # if self.error_alternative is not None:
        #     self.error_alternative(error)
        # else:
        #     raise Exception(error)

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
        elif isinstance(http_method, HTTPMethodEnum):
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
    def set_url(self, http_url=None, session_wide=False):
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
                self.set_query_parameters(parsed_url.query, session_wide)

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
        @session_wide
            If this is true then the session object will be used instead of the requests object

        ** Affects: Session and Request Object **
    """
    def set_query_parameters(self, parameters=None, session_wide=False):
        _parameters = parameters

        # Clear query parameters
        if parameters is None and session_wide is False:
            self.request_object.params = {}
        elif parameters is None and session_wide is True:
            self.session.params.clear()

        # If the supplied query params is a string, We then attempt to parse it into a dict
        elif isinstance(parameters, str):
            _parameters = request._split_string_into_dict(parameters, "&", "=")

        # Apply to the session object
        if isinstance(_parameters, dict) and session_wide is True:
            self.session.params.update(_parameters)

        # Apply to the request object
        elif isinstance(_parameters, dict) and session_wide is False:
            self.request_object.params = _parameters

        else:
            # Clear query parameters
            if session_wide is False:
                self.request_object.params = {}
            elif session_wide is True:
                self.session.params.clear()

            self.handle_error("Invalid query parameters specified")

    """
        Returns the current state of the query parameters
        ** Affects: None **
    """
    def get_query_parameters(self, session_wide=False):
        if session_wide is True:
            return self.session.params
        else:
            return self.request_object.params

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
        # A Request method is required first to determine if a body is required
        if self.request_object.method is None:
            print("Please define the request type before supplying a body")
            self.request_object.data = []
            return

        # Get the request method
        request_method = HTTPMethodEnum[self.request_object.method] \
            if self.request_object.method in self.request_method_enum_list else None

        # Use the request method to determine if this request requires a body
        if request_method is not None and request_method.value:
            if request_method.value["body"] is not True:
                print("Request method does not take a body")
                self.request_object.data = []
                return
        else:
            print("Invalid request method")
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
                print("Invalid body, Does not match schematic")
                self.request_object.data = []

    """
        Returns the current state of the body
        ** Affects: None **
    """
    def get_body(self):
        return self.request_object.data

    """
        Apply a dict to the active request object or session object

        @headers
            A dict containing all the header key value pairs
        @session_wide
            If this is true then the session object will be used instead of the requests object
    """
    def set_headers(self, headers=None, session_wide=False):
        # Apply to the session
        if isinstance(headers, dict) and session_wide is True:
            self.session.headers.update(headers)
        # Apply to the request object
        elif isinstance(headers, dict) and session_wide is False:
            self.request_object.headers = headers
        # Wipe the variable
        else:
            self.request_object.headers = {}

    """
        Returns the current state of the headers
        ** Affects: None **
    """
    def get_headers(self, session_wide=False):
        if session_wide:
            return self.session.headers
        else:
            return self.request_object.headers

    """

        @schematic
        @details
        @session_wide
    """
    def set_auth(self, schematic=None, details=None, session_wide=False):
        # Reset session auth
        if (schematic is None or schematic.value is HTTPAuthenticationType.NoAuth) and session_wide is True:
            self.session.auth = None

        # Reset request object auth
        elif (schematic is None or schematic.value is HTTPAuthenticationType.NoAuth) and session_wide is False:
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
                if schematic is HTTPAuthenticationType.BasicAuth and session_wide is True:
                    self.session.auth = HTTPBasicAuth(data.username, data.password)

                # Apply request data
                elif schematic is HTTPAuthenticationType.BasicAuth and session_wide is False:
                    self.request_object.auth = HTTPBasicAuth(data.username, data.password)

            # If validation failed
            except DataError as e:
                print(e)
                print("Auth details does not match the schematic")
                if session_wide is True:
                    self.session.auth = None
                else:
                    self.request_object.auth = None
        else:
            self.handle_error("Invalid authentication method supplied")

    """
        Returns the current state of the auth
        ** Affects: None **
    """
    def get_auth(self, session_wide=False):
        if session_wide is True:
            return self.session.auth
        else:
            return self.request_object.auth

    """

        @proxies
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
            print("Invalid proxy details")

    """
        Returns the current state of the proxy
        ** Affects: None **
    """
    def get_proxy(self):
        return self.session.proxies

    """

        @timeout
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
    """
    def send(self):
        prepared = self.request_object.prepare()
        return self.session.send(prepared, timeout=self.timeout)


"""
Flow Example
"""

request = HTTPHelper()

# def post_200_0_headers_body_json():
#     request = HTTPHelper()
#     request.set_method("POST")
#     request.set_url("https://http-handle.free.beeceptor.com/post/200/0/headers/body/json/v1")
#     request.set_http_request_body({
#         'title': 'foo',
#         'body': 'bar',
#         'userId': 1
#     }, HTTPRequestType.JSON, TypiCodeCreateResource)
#     request.set_http_headers({
#         'Content-type': 'application/json'
#     })
#     response = request.send_request()
#     print(response.status_code)
#     print(response.content)


# post_200_0_headers_body_json()
