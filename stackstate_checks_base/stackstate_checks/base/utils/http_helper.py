# coding=utf-8

import json
import requests_mock
import logging
from enum import Enum
from schematics.models import Model
from schematics.types import BaseType, StringType, IntType, DictType, BooleanType
from schematics.exceptions import DataError
from requests import Session, Request
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from ..utils.common import to_string

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


http_method_choices = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
authentication_choices = ['basic']


class HTTPRequestType(Enum):
    JSON = dict


class HTTPResponseType(Enum):
    PLAIN = str
    JSON = dict


class HTTPHelperModel(Model):
    """
        This is the model for the `HTTPHelper` class.
        When using the `HTTPHelper` class there will be the only acceptable values to create state and kick off the
        request
    """
    mock_enable = BooleanType(required=False, default=False)
    mock_status = IntType(required=False, default=None)
    mock_text = BaseType(required=False, default=None)
    endpoint = StringType(required=True, default=None)
    auth_data = DictType(BaseType, required=False, default=None)
    auth_type = StringType(required=False, choices=authentication_choices, default=None)
    session_auth_data = BaseType(required=False, default=None)
    session_auth_type = StringType(required=False, choices=authentication_choices, default=None)
    body = BaseType(required=False, default=None)
    proxy = BaseType(required=False, default=None)
    headers = DictType(StringType, required=False, default=None)
    session_headers = DictType(StringType, required=False, default=None)
    query = DictType(StringType, required=False, default=None)
    timeout = IntType(required=False, default=None)
    ssl_verify = BooleanType(required=False, default=True)
    retry_policy = BaseType(required=False, default=None)
    request_schematic_validation = BaseType(required=False, default=None)
    request_type_validation = BaseType(required=False, default=None)
    response_status_code_validation = IntType(required=False, default=None)
    response_type_validation = BaseType(required=False, default=None)
    response_schematic_validation = BaseType(required=False, default=None)


class HTTPHelper:
    """
        The HTTP Helper Handler is used to create compact methods using most of the function defined in the
        Connection, Request, Session and Response Helpers
        Functionality:
            - GET Request
            - POST Request
            - DELETE Request
            - PATCH Request
            - PUT Request

        All the HTTPHelper classes and Sub classes can accept a schematic dictionary that allows certain values to
        manipulate state with
    """
    log = logging.getLogger('%s.base' % __name__)

    def __init__(self):
        pass

    def get(self, http_model, session_handler=None):
        return self._build_validate_and_execute("GET", HTTPHelperModel(http_model), session_handler)

    def post(self, http_model, session_handler=None):
        return self._build_validate_and_execute("POST", HTTPHelperModel(http_model), session_handler)

    def put(self, http_model, session_handler=None):
        return self._build_validate_and_execute("PUT", HTTPHelperModel(http_model), session_handler)

    def delete(self, http_model, session_handler=None):
        return self._build_validate_and_execute("DELETE", HTTPHelperModel(http_model), session_handler)

    def patch(self, http_model, session_handler=None):
        return self._build_validate_and_execute("PATCH", HTTPHelperModel(http_model), session_handler)

    def _build_validate_and_execute(self, active_method, http_model, session_handler=None):
        """
        Functionality:
            A generic builder to contains most of the functionality on the Connection, Request, Session and Response
            Helpers. This function will be used by compact methods to build up a request

        Input:
            @active_method
                The active HTTP method for example GET or POST
            @helper_model
                Lorem ipsum
        """

        self.log.info("Executing the HTTPHelper {0} function with the following properties: {1}"
                      .format(str(active_method), str(http_model)))

        connection = HTTPHelperConnectionHandler({
            "timeout": http_model.timeout,
            "ssl_verify": http_model.ssl_verify,
            "retry_policy": http_model.retry_policy,
            "proxy": http_model.proxy,
        })

        session = session_handler if type(session_handler) is HTTPHelperSessionHandler else HTTPHelperSessionHandler({
            "headers": http_model.session_headers,
            "auth_data": http_model.session_auth_data,
            "auth_type": http_model.session_auth_type,
            "mock_enable": http_model.mock_enable,
            "mock_status": http_model.mock_status,
            "mock_text": http_model.mock_text
        })

        request = HTTPHelperRequestHandler({
            "method": active_method,
            "endpoint": http_model.endpoint,
            "query": http_model.query,
            "headers": http_model.headers,
            "body": http_model.body,
            "auth_data": http_model.auth_data,
            "auth_type": http_model.auth_type,
            "request_schematic_validation": http_model.request_schematic_validation,
            "request_type_validation": http_model.request_type_validation,
        })

        # Run Validation
        self.log.info("Running connection, session and request validation")
        connection.validate_connection_model()
        session.validate_session_model()
        request.validate_request_model()

        # Send the request to the endpoint
        request_response = connection.send(session, request)
        self.log.info("Received the following response from the external endpoint: {0}".format(request_response))

        response_handler = HTTPHelperResponseHandler({
            "response": request_response,
            "response_status_code_validation": http_model.response_status_code_validation,
            "response_type_validation": http_model.response_type_validation,
            "response_schematic_validation": http_model.response_schematic_validation,
        })

        # Run Validation
        self.log.info("Attempting to validate the response")
        response_handler.validate_response_model()
        response_handler.validate_status_code()

        return response_handler


class HTTPHelperRequestModel(Model):
    """
        This is the model for the `HTTPHelperRequestHandler` class.
        When using the `HTTPHelperRequestHandler` class there will be the only acceptable values to create state, This
        state can in turn be used within the HTTPHelper class
    """
    method = StringType(required=True)
    endpoint = StringType(required=True, default=None)
    query = DictType(StringType, default=dict({}))
    headers = DictType(StringType, default=dict({}))
    body = BaseType(required=False, default=None)
    auth_data = DictType(BaseType, required=False, default=None)
    auth_type = StringType(required=False, choices=authentication_choices, default=None)
    request_schematic_validation = BaseType(required=False, default=None)
    request_type_validation = BaseType(required=False, default=None)


class HTTPHelperRequestHandler:
    """
        The HTTP Helper Request Handler is used to control the state of the Request() object within the requests library
        Anything that can manipulate, create or fetch the state from this Request() object should be contained within,
        Functionality:
            - Create, Retrieve and maintain the HTTPHelperRequestModel() object
            - SET && VALIDATE HTTP Method
            - SET && VALIDATE HTTP Endpoint
            - SET && VALIDATE HTTP Query Parameters
            - SET && VALIDATE HTTP Body
            - SET && VALIDATE HTTP Validation
            - SET && VALIDATE HTTP Headers
            - SET && VALIDATE HTTP Auth
    """
    _request_types = [item.value for item in HTTPRequestType]
    log = logging.getLogger('%s.request_handler' % __name__)

    def __init__(self, request_model=None):
        # Receive a model or create one if not specified
        self._request_model = HTTPHelperRequestModel(request_model) if request_model is not None \
            else HTTPHelperRequestModel()

    def get_request_model(self):
        """
        Functionality:
            Display the current request model inside this class. This model will be used to create the Request() object
            for the requests library
        """
        return self._request_model

    def validate_request_model(self):
        """
        Functionality:
            We can also run a validation against the model as this model is a schematic
        """
        self._request_model.validate()

    def create_request_object(self):
        """
        Functionality:
            We attempt to create the Request() object and apply the correct data to it.
            We also run the validation to make sure that all the data we are applying is correct
        """
        request_object = Request()

        # Run internal validation to first determine if the body schema and type is correct
        self.validate_body_schematic()
        self.validate_body_type()

        # Method Apply and validation
        self.validate_method()
        request_object.method = self._request_model.method

        # URL Apply and validation
        self.validate_endpoint()
        request_object.url = self._request_model.endpoint

        # Query Apply and validation
        self.validate_query_param()
        request_object.params = self._request_model.query

        # Headers Apply and validation
        self.validate_headers()
        request_object.headers = self._request_model.headers

        # Body Apply and validation
        self.validate_body()
        request_object.data = self._request_model.body

        # Authentication Apply and validation
        self.validate_auth()
        request_object.auth_data = self._request_model.auth_data
        request_object.auth_type = self._request_model.auth_type

        return request_object

    def validate_method(self):
        """
        Functionality:
            Validate the state of the method to determine if the applied value to the method object is correct
        """
        if self._request_model.method is None:
            message = """The http method has not been applied"""
            raise ValueError(message)

        # String Check
        # If the value was not found in a enum then we attempt to find the enum that contains the same as the
        # string value provided.
        # The following checks are made
        # - Is the method passed a string so that we can match it in the enum
        # - Does that string exist in the mapped enum list.
        if self._request_model.method in http_method_choices:
            self.log.info("String method found inside the `http_method_choices` array, Applying {0} as the active"
                          "method.".format(str(self._request_model.method)))
            return True

        # If we do not find the value inside the enum then it means that we do not support the method yet
        else:
            message = """Unable to find the provided {0} method. Currently the code
                         block only supports the methods provided in the http_method_choices
                         array. If you would like to add another method feel free to add it
                         within the http_method_choices array or change the supplied {1} to a
                         supported type""".format(str(self._request_model.method), str(self._request_model.method))
            raise NotImplementedError(message)

    def validate_endpoint(self):
        """
        Functionality:
            Validate the state of the endpoint to determine if the applied value to the url object is correct
        """
        if self._request_model.endpoint is None:
            message = """The endpoint url has not been applied"""
            raise ValueError(message)

        return True

    def validate_query_param(self):
        """
        Functionality:
            Validate the state of the query param to determine if the applied value is a dict
        """
        if isinstance(self._request_model.query, dict) or self._request_model.query is None:
            return True

        else:
            message = """The parameters provided does not contain the correct type.
                         The provided type is {0}. This function only accepts dict
                         objects this allows a easy mapping to the query object as the parameters
                         also exists out of key and value pairs.
                         To fix this please look at the {1} object or remove the query parameters""" \
                .format(str(type(self._request_model.query)), str(self._request_model.query))
            raise TypeError(message)

    @staticmethod
    def validate_body():
        """
        Functionality:
            Validate the state of the body.
            Currently we are passing any body nothing is seen as invalid.

            This is implemented for future use if required
        """
        return True

    def validate_headers(self):
        """
        Functionality:
            Validate the state of the headers to determine if the applied value is a dict
        """
        if isinstance(self._request_model.headers, dict) or self._request_model.headers is None:
            return True
        else:
            message = """The headers provided does not contain the correct type.
                         The provided type is {0}. This function only accepts dict
                         objects this allows a easy mapping to the query object as the headers
                         also exists out of key and value pairs. The current headers passed
                         was the following {1}""".format(str(type(self._request_model.headers)),
                                                         str(self._request_model.headers))
            raise TypeError(message)

    def validate_auth(self):
        return validate_auth(self._request_model.auth_type,
                             self._request_model.auth_data)

    def validate_body_type(self):
        if self._request_model.request_type_validation is None:
            return True

        # Validate that the `body_type` parameter is a instance of the `HTTPRequestType` enum
        elif isinstance(self._request_model.request_type_validation, Enum) and \
                hasattr(self._request_model.request_type_validation, "value") and \
                self._request_model.request_type_validation.value in self._request_types and \
                issubclass(self._request_model.request_type_validation.value, type(self._request_model.body)):
            return True

        else:
            message = """The body does not conform to the body type provided ({0}).
                         Either the body type passed to the `validate_body` function needs to be
                         changed, The validation needs to be removed to allow this body type or
                         the body needs to be looked at and why it is passing down the incorrect data.
                         The current body tested content is {1}""".format(
                str(self._request_model.request_type_validation),
                str(self._request_model.body))
            raise ValueError(message)

    def validate_body_schematic(self):
        if self._request_model.request_schematic_validation is None:
            return True

        # If the HTTP Response Validation Schematic has been set
        else:
            try:
                # The last part to test is does the Parsed JSON match the schematic validation
                self._request_model.request_schematic_validation(self._request_model.body) \
                    .validate()
                return True

            except DataError as e:
                message = """The request was unable to conform to the validation schematic.
                             The error provided by the schematic validation is {0}
                             To fix this you can either modify the schematic validation or remove it entirely
                             """.format(str(e))
                raise DataError(message)

            except TypeError as e:
                message = """The request was unable to conform to the validation schematic. The
                             schematic applied was {0}
                             The error provided by the schematic validation is {1}
                             To fix this you can either modify the schematic validation or remove it entirely
                             """.format(str(self._request_model.request_schematic_validation), e)
                raise TypeError(message)

    def create_basic_auth(self):
        return HTTPBasicAuth(self._request_model.auth_data.get('username'),
                             self._request_model.auth_data.get('password'))


class HTTPHelperSessionModel(Model):
    """
        This is the model for the `HTTPHelperSessionHandler` class.
        When using the `HTTPHelperSessionHandler` class there will be the only acceptable values to create state, This
        state can in turn be used within the HTTPHelper class
    """
    mock_enable = BooleanType(required=False, default=False)
    mock_status = IntType(required=False, default=None)
    mock_text = BaseType(required=False, default=None)
    headers = DictType(StringType, default=dict({}))
    auth_data = BaseType(required=False, default=None)
    auth_type = StringType(required=False, choices=authentication_choices, default=None)


class HTTPHelperSessionHandler:
    """
        The HTTP Helper Session Handler is used to control the state of the Session() object within the requests library
        Anything that can manipulate, create or fetch the state from this Session() object should be contained within,
        Functionality:
            - Create and maintain the Session() object from requests
            - SET Mount Adaptor for unit testing
            - SET && GET HTTP Headers
            - SET && GET HTTP Auth
    """

    log = logging.getLogger('%s.session_handler' % __name__)

    def __init__(self, session_model=None):
        self._session_model = HTTPHelperSessionModel(session_model) if session_model is not None \
            else HTTPHelperSessionModel()

    def get_session_model(self):
        """
        Functionality:
            Display the current request model inside this class. This model will be used to create the Request() object
            for the requests library
        """
        return self._session_model

    def validate_session_model(self):
        """
        Functionality:
            We can also run a validation against the model as that model is a schematic
        """
        self._session_model.validate()

    def create_session_object(self):
        """
        Functionality:
            We attempt to create the Request() object and apply the correct data to it.
            We also run the validation to make sure that all the data we are applying is correct
        """
        session_object = Session()

        # Headers Apply and validation
        self.validate_headers()
        session_object.headers = self._session_model.headers

        # Authentication Apply and validation
        self.validate_auth()
        session_object.auth_type = self._session_model.auth_type
        session_object.auth_data = self._session_model.auth_data

        return session_object

    def validate_headers(self):
        """
        Functionality:
            Validate the state of the headers to determine if the applied value is a dict
        """
        if isinstance(self._session_model.headers, dict) or self._session_model.headers is None:
            return True
        else:
            message = """The headers provided does not contain the correct type.
                         The provided type is {0}. This function only accepts dict
                         objects this allows a easy mapping to the query object as the headers
                         also exists out of key and value pairs. The current headers passed
                         was the following {1}""".format(str(type(self._session_model.headers)),
                                                         str(self._session_model.headers))
            raise TypeError(message)

    def validate_auth(self):
        return validate_auth(self._session_model.auth_type,
                             self._session_model.auth_data)

    def create_basic_auth(self):
        return HTTPBasicAuth(self._session_model.auth_data.get('username'),
                             self._session_model.auth_data.get('password'))


class HTTPHelperConnectionModel(Model):
    """
        This is the model for the `HTTPHelperConnectionHandler` class.
        When using the `HTTPHelperConnectionHandler` class there will be the only acceptable values to create state,This
        state can in turn be used within the HTTPHelper class
    """
    timeout = IntType(required=False, default=None)
    ssl_verify = BooleanType(required=False, default=True)
    retry_policy = BaseType(required=False, default=None)
    proxy = BaseType(required=False, default=None)


class HTTPHelperConnectionHandler:
    """
        The HTTP Helper Connection Handler is used to control the state of the connection outside of the Session() and
        Request() object state.
        Anything that can manipulate, create or fetch the state of the session should be contained within,
        Functionality:
            - Create and maintain the connection values outside of the Session() and Request() objects
            - SET && GET HTTP Timeout
            - SET && GET HTTP Retry Policy
            - SET && GET HTTP SSL Verification
            - SET && GET HTTP Proxy
            - Sending the HTTP Request and Session to the Endpoint
    """
    log = logging.getLogger('%s.connection_handler' % __name__)

    def __init__(self, connection_model=None):
        self._connection_model = HTTPHelperConnectionModel(connection_model) if connection_model is not None \
            else HTTPHelperConnectionModel()

    def get_connection_model(self):
        """
        Functionality:
            Display the current request model inside this class. This model will be used to create the Request() object
            for the requests library
        """
        return self._connection_model

    def validate_connection_model(self):
        """
        Functionality:
            We can also run a validation against the model as that model is a schematic
        """
        self._connection_model.validate()

    def validate_retry_policy(self):
        if self._connection_model.retry_policy is None:
            return True

        elif isinstance(self._connection_model.retry_policy, dict):
            Retry(**self._connection_model.retry_policy)
            return True

        return False

    def validate_proxy(self):
        if isinstance(self._connection_model.proxy, dict) or self._connection_model.proxy is None:
            return True

        else:
            message = """The proxy provided does not contain the correct type.
                         The provided type is {0}. This function only accepts dict
                         objects this allows a easy mapping to the proxy object as the proxy
                         also exists out of key and value pairs""".format(str(type(self._connection_model.proxy)))
            raise TypeError(message)

    def send(self, session_handler, request_handler):
        """
        Functionality:
            This function is used to make the request.
            On call the retry policy, timeout, ssl verify is applied.
            After the request responds, That response will be tested against response validation

        Input:
            @session_handler
                The Session Handler Class. This allows the user to also pass down a custom session handler if required
            @request_handler
                The Request Handler Class. This allows the user to also pass down a custom request handler if required
        """

        session = session_handler.create_session_object()
        request = request_handler.create_request_object()

        # Mock requests
        if session_handler.get_session_model().mock_enable is True:
            adapter = requests_mock.Adapter()
            session.mount('mock://', adapter)
            adapter.register_uri(request_handler.get_request_model().method,
                                 str(request_handler.get_request_model().endpoint),
                                 status_code=session_handler.get_session_model().mock_status,
                                 text=session_handler.get_session_model().mock_text)
            session.mount('mock://', adapter)

        # Apply the retry policy
        if self._connection_model.retry_policy is not None:
            adapter = HTTPAdapter(max_retries=self._connection_model.retry_policy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)

        # Apply the proxy
        if self._connection_model.proxy is not None:
            session.proxies = self._connection_model.proxy

        # Apply the ssl verification
        if self._connection_model.ssl_verify is not None:
            session.verify = self._connection_model.ssl_verify

        # Auth will already have gone through validation thus we just test types and apply values
        # Request - HTTPBasicAuth
        if request_handler.get_request_model().auth_type == "basic":
            request.auth = request_handler.create_basic_auth()

        # Session - HTTPBasicAuth
        if session_handler.get_session_model().auth_type == "basic":
            session.auth = session_handler.create_basic_auth()

        return session.send(request.prepare(), timeout=self._connection_model.timeout)


class HTTPHelperResponseModel(Model):
    """
        This is the model for the `HTTPHelperResponseHandler` class.
        When using the `HTTPHelperResponseHandler` class there will be the only acceptable values to create state,This
        state can in turn be used within the HTTPHelper class
    """
    response = BaseType(required=False, default=None)
    response_status_code_validation = IntType(required=False, default=None)
    response_type_validation = BaseType(required=False, default=None)
    response_schematic_validation = BaseType(required=False, default=None)


class HTTPHelperResponseHandler:
    """
        The HTTP Helper Response Handler is used to validate the response content
        Anything that can manipulate, create or fetch the state of the response.
        Functionality:
            - Create and maintain the connection values outside of the Session() and Request() objects
            - SET && GET HTTP Timeout
            - SET && GET HTTP Retry Policy
            - SET && GET HTTP SSL Verification
            - Sending the HTTP Request and Session to the Endpoint

    """

    _response_types = [item.value for item in HTTPResponseType]

    log = logging.getLogger('%s.response_handler' % __name__)

    def __init__(self, response_model=None):
        self._response_model = HTTPHelperResponseModel(response_model) if response_model is not None \
            else HTTPHelperResponseModel()

    def get_status_code(self):
        """
        Return the status code response from the executed Session() object
        """
        return self._response_model.response.status_code

    def get_json(self):
        """
        First we attempt to decode the json then we run validation on the data.
        This will then return valid decoded json from the execute Session() object
        """
        # We first decode the response with the encoding header
        decoded_response = self._response_model.response.content.decode(
            self._response_model.response.encoding
        )

        ensured_string_values = to_string(decoded_response)

        # Next we use the json load function with its build-in unicode functionality to decode the object
        # This will work on straight text or json objects
        # This should take the object from a unicode state to a dict state
        json_decoded_response = json.loads(ensured_string_values)

        # If valid json was found return this json
        # Run validation before we return the value
        if issubclass(type(json_decoded_response), dict) and self.validate_body_schematic(json_decoded_response):
            return json_decoded_response
        else:
            return None

    def get_request_method(self):
        """
        Return the request method from the executed Session(Request()) object
        """
        return self._response_model.response.request.method

    def get_request_url(self):
        """
        Return the url from the executed Session(Request()) object
        """
        return self._response_model.response.request.url

    def get_request_headers(self):
        """
        Return the headers from the executed Session(Request()) object
        """
        return self._response_model.response.request.headers

    def validate_response_model(self):
        """
        Functionality:
            We can also run a validation against the model as that model is a schematic
        """
        self._response_model.validate()

    def validate_body_schematic(self, json_decoded_response):
        if self._response_model.response_schematic_validation is None or \
                self._response_model.response is None:
            return True

        if issubclass(self._response_model.response_schematic_validation, Model) is True:
            try:
                if isinstance(json_decoded_response, dict) is False:
                    raise ValueError()

                # The last part to test is does the Parsed JSON match the schematic validation
                self._response_model.response_schematic_validation(json_decoded_response) \
                    .validate()

                return True

            except DataError as e:
                message = """The response was unable to conform to the validation schematic.
                             The error provided by the schematic validation is {0}
                             To fix this you can either modify the schematic validation or remove it entirely
                             """.format(str(e))
                raise DataError(message)

            except ValueError as e:
                message = """Unable to parse the response as JSON.
                             The response received was {0}.
                             Full error from the JSON parse attempt {1}
                             """.format(str(self._response_model.response.content), e)
                raise ValueError(message)

        else:
            message = """The proxy schematic does not contain the correct type.
                         The provided type is {0}. The function requires a valid schematic as a argument
                         This allows a response object to be tested against the schematic""" \
                .format(str(type(self._response_model.response_schematic_validation)))
            raise TypeError(message)

    def validate_status_code(self):
        if self._response_model.response_status_code_validation is None:
            return True

        if isinstance(self._response_model.response_status_code_validation, int):
            if self._response_model.response.status_code != self._response_model.response_status_code_validation:
                message = """The response was unable to conform to the validation status code. The status code
                             applied was {0} The expected status code is {1}
                             To fix this you can either modify the status code validation or remove it entirely
                             """.format(str(self._response_model.response.status_code),
                                        str(self._response_model.response_status_code_validation))
                raise ValueError(message)

            # If the status code has not been set then we will by default see 400 > as bad responses.
            else:
                return True

        else:
            message = """The proxy schematic does not contain the correct type.
                         The provided type is {0}. The function requires a int to test the response
                         status code against""".format(str(type(self._response_model.response_status_code_validation)))
            raise TypeError(message)


def validate_auth(auth_type, auth_data):
    """
    Functionality:
        Validate the state of the two auth objects that will be used to apply authentication
        Test if the auth_schematic passed
        We also do a second test to make sure the auth_schematic.value is also a model
    """
    if auth_type is None and auth_data is None:
        return True

    if auth_type in authentication_choices and auth_type == "basic":
        if auth_data.get('username') is None or auth_data.get('password') is None:
            message = """For the Basic Authentication a username and password is required. The
                         current authentication data passed to this function is incorrect. The authentication
                         data is {0}""".format(str(auth_data))
            raise DataError(message)

        HTTPBasicAuth(auth_data.get('username'),
                      auth_data.get('password'))
        return True

    else:
        message = """We are unable to find the authentication defined within the http_method_choices var.
                     Please verify if the authentication type {0} exists within the http_method_choices
                     variable. If it does not then you need to either change the authentication type
                     or add the authentication variable inside the http_method_choices var""" \
            .format(str(auth_type))
        raise NotImplementedError(message)
