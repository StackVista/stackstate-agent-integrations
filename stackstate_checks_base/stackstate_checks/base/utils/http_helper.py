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

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class HTTPBasicAuthentication(Model):
    username = StringType(required=True)
    password = StringType(required=True)


class HTTPAuthenticationType(Enum):
    BasicAuth = HTTPBasicAuthentication


class HTTPMethod(Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'


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
    mock_response = BaseType(required=False, default=None)
    endpoint = StringType(required=True, default=None)
    auth_data = DictType(BaseType, required=False, default=None)
    auth_type = BaseType(required=False, default=None)
    session_auth_data = BaseType(required=False, default=None)
    session_auth_type = BaseType(required=False, default=None)
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

    def __init__(self):
        self.log = logging.getLogger('%s.base' % __name__)

    def get(self, http_model):
        return self._builder("GET", HTTPHelperModel(http_model))

    def post(self, http_model):
        return self._builder("POST", HTTPHelperModel(http_model))

    def put(self, http_model):
        return self._builder("PUT", HTTPHelperModel(http_model))

    def delete(self, http_model):
        return self._builder("DELETE", HTTPHelperModel(http_model))

    def patch(self, http_model):
        return self._builder("PATCH", HTTPHelperModel(http_model))

    def _builder(self, active_method, http_model):
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

        session = HTTPHelperSessionHandler({
            "headers": http_model.session_headers,
            "auth_data": http_model.session_auth_data,
            "auth_type": http_model.session_auth_type,
            "mock_enable": http_model.mock_enable,
            "mock_status": http_model.mock_status,
            "mock_response": http_model.mock_response
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

        response = HTTPHelperResponseHandler({
            "response_status_code_validation": http_model.response_status_code_validation,
            "response_type_validation": http_model.response_type_validation,
            "response_schematic_validation": http_model.response_schematic_validation,
        })

        request_response = connection.send(session, request)

        self.log.info("Received the following response from the external endpoint: {0}"
                      .format(request_response))

        self.log.info("Attempting to validate the response content")

        response.validate_body_schematic(request_response)
        response.validate_status_code(request_response)
        response.validate_body_type(request_response)

        return request_response


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
    auth_type = BaseType(required=False, default=None)
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
    _request_model = HTTPHelperRequestModel()
    _authentication_types = [item.value for item in HTTPAuthenticationType]
    _request_types = [item.value for item in HTTPRequestType]
    _http_method_enums = [item.value for item in HTTPMethod]

    def __init__(self, request_model=None):
        self.log = logging.getLogger('%s.request_handler' % __name__)
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
        request_object.auth_data = self._request_model.auth_data
        request_object.auth_type = self._request_model.auth_type

        return request_object

    def _set_method(self, method):
        """
        Functionality:
            Set the current HTTP Method for the Requests() object from the HTTPMethod enum or String equivalent from the
            HTTPMethod enum. If a method is specified which does not exist in the HTTPMethod a
            `Not Implemented` error will be triggered.

        Input:
            @method
                This can either be a value from the `HTTPMethod` or a direct string that can be mapped to the
                `HTTPMethod` The value of this will be the type of request made for example POST or GET
        """

        self.log.info("Attempting to set the active http method to {0}".format(str(method)))
        self._request_model.method = method

    def validate_method(self):
        """
        Functionality:
            Validate the state of the method to determine if the applied value to the method object is correct
        """
        if self._request_model.method is None:
            message = """The http method has not been applied"""
            self.log.error(message)
            raise ValueError(message)

        # ENUM Check
        # We attempt to see if the provided variable exists inside the enum
        # The following checks are made
        # - Is the method a enum value
        # - Does the method exist in the enum
        # - Can we get the value data from the method
        elif isinstance(self._request_model.method, Enum) and \
                hasattr(self._request_model.method, "value") and \
                self._request_model.method.value in self._http_method_enums:
            self.log.info("Enum Method found inside the `HTTPMethod` enum, Applying {0} as the active"
                          "method.".format(str(self._request_model.method.value)))
            return True

        # String Check
        # If the value was not found in a enum then we attempt to find the enum that contains the same as the
        # string value provided.
        # The following checks are made
        # - Is the method passed a string so that we can match it in the enum
        # - Does that string exist in the mapped enum list.
        elif self._request_model.method in self._http_method_enums:
            self.log.info("String method found inside the `HTTPMethod` enum, Applying {0} as the active"
                          "method.".format(str(self._request_model.method)))
            return True

        # If we do not find the value inside the enum then it means that we do not support the method yet
        else:
            message = """Unable to find the provided {0} method. Currently the code
                         block only supports the methods provided in the `HTTPMethod`
                         Enum. If you would like to add another method feel free to add it
                         within the `HTTPMethod` Enum or change the supplied {1} to a
                         supported type""".format(str(self._request_model.method), str(self._request_model.method))
            self.log.error(message)
            raise NotImplementedError(message)

    def _set_endpoint(self, endpoint):
        """
        Functionality:
            The endpoint is set with this function.
            Some extra functionality is build-into this function to analyze a URL. When something like the following is
            passed to the function 'http://www.url.com?test=123' the query parameters on this URL will be split out and
            applied into the correct object within the Request() object

        Input:
            @url
                A string object containing the endpoint that should be queried
        """
        if isinstance(endpoint, str):
            # We deconstruct the URL at this point.
            # This allows us to piece it back together with only what we need.
            parsed_endpoint = urlparse.urlparse(endpoint)
            self.log.info("Endpoint parsed successfully, Result is as follow {0}".format(str(parsed_endpoint)))

            # The URL is recreated here by adding the schema, net location and path together
            self._request_model.url = ((parsed_endpoint.scheme + "://" if len(parsed_endpoint.scheme) > 0 else "") +
                                       parsed_endpoint.netloc +
                                       parsed_endpoint.path)
            self.log.info("Reconstructed URL {0}".format(str(self._request_model.url)))

            # If we found any extra data within the URL we then attempt to map it to the correct location
            if parsed_endpoint.query is not None and len(parsed_endpoint.query) > 0:
                query_dict = self.split_string_into_dict(parsed_endpoint.query, "&", "=")
                # Apply the extracted parameters into the Request() object
                self._request_model.query = query_dict

        # Invalid URL
        else:
            message = """The URL provided is incorrect, The type provided is {0} and the value is
                         {1} .The URL needs to be parsed thus we need a string to be able to parse
                         the URL""".format(str(type(endpoint)), str(endpoint))
            self.log.error(message)
            raise TypeError(message)

    def validate_endpoint(self):
        """
        Functionality:
            Validate the state of the endpoint to determine if the applied value to the url object is correct
        """
        if self._request_model.endpoint is None:
            message = """The endpoint url has not been applied"""
            self.log.error(message)
            raise ValueError(message)

        return True

    def _set_query_param(self, query):
        """
        Functionality:
            This function controls the state of the HTTP Query Parameters object.

        Input:
            @parameters
                A basic dict object mapping values to keys
        """
        self.log.info("Attempting to set the active query parameters to {0}".format(str(self._request_model.query)))
        self._request_model.query = query

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
            self.log.error(message)
            raise TypeError(message)

    def _set_body(self, body):
        """
        Functionality:
            Apply a body to the Request() object.
            We do not restrict the body type as you may wish to send something other than a JSON object

        Input:
            @body
                A body containing any data you want to send to the HTTP Endpoint
        """
        self.log.info("Attempting to set the active data object to {0}".format(str(body)))
        self._request_model.body = body

    @staticmethod
    def validate_body():
        """
        Functionality:
            Validate the state of the body.
            Currently we are passing any body nothing is seen as invalid.

            This is implemented for future use if required
        """
        return True

    def _set_headers(self, headers):
        """
        Functionality:
            Apply a dict object containing values for the headers to the Request() object.

        Input:
            @headers
                A dict object containing the key values for the headers,
        """
        self.log.info("Attempting to set the headers to {0}".format(str(self._request_model.headers)))
        self._request_model.headers = headers

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
            self.log.error(message)
            raise TypeError(message)

    def _set_auth(self, auth_type, auth_data):
        """
        Functionality:
            Apply authentication to the Request() object.
            A type structure and data structure is required to apply a authentication

        Input:
            @auth_schematic
                A value from the `HTTPAuthenticationType` enum
            @auth_details
                Dict containing the information required from the @auth_schematic `HTTPAuthenticationType` enum object

        We need to validate the authentication on apply the value as we need to create the correct auth model from
        the specified values
        """
        self.log.info("Attempting to set the authentication to {0} with the following schematic model {1}"
                      .format(str(auth_data), str(auth_type)))
        self._request_model.auth_data = auth_data
        self._request_model.auth_type = auth_type

    def validate_auth(self):
        """
        Functionality:
            Validate the state of the two auth objects that will be used to apply authentication
            Test if the auth_schematic passed does exist in the HTTPAuthenticationType enum
            We also do a second test to make sure the auth_schematic.value is also a model
        """
        if isinstance(self._request_model.auth_type, Enum) and \
                self._request_model.auth_type.value in self._authentication_types and \
                issubclass(self._request_model.auth_type.value, Model):
            try:
                # Validate the schematic object with the current authentication details
                self._request_model.auth_type.value(self._request_model.auth_data).validate()

                # We need to manually map the supported types to the correct object for the Request() auth
                if self._request_model.auth_type is HTTPAuthenticationType.BasicAuth:
                    HTTPBasicAuth(self._request_model.auth_data.get('username'),
                                  self._request_model.auth_data.get('password'))
                    return True
                else:
                    message = """We are unable to map the enum `HTTPAuthenticationType`
                                 to the request auth object. Please verify if the object exists in the
                                 HTTPAuthenticationType enum and if it does then the mapping for {0}
                                 is missing from the _set_auth function. You need to add a check for
                                 the enum and map the values over to the requests object""" \
                        .format(str(self._request_model.auth_type))
                    self.log.error(message)
                    raise NotImplementedError(message)

            except DataError as e:
                message = """The authentication supplied {0} does not match the required
                             schema {1}. You can view the layout of the schema on the
                             `HTTPAuthenticationType` enum.

                             The error provided by the execution
                             {2}""".format(str(self._request_model.auth_data), str(self._request_model.auth_type), e)
                self.log.error(message)
                raise e

            except TypeError as e:
                message = """The authentication details object passed to this function failed as
                             the type of this object is incorrect. The type passed down was
                             {0} and the expected type is a iterable value that matches the
                             `HTTPAuthenticationType` enum

                             The error provided by the execution
                             {1}""".format(type(self._request_model.auth_data), e)
                self.log.error(message)
                raise TypeError(message)

        else:
            message = """The `auth_schematic` variable passed to the `_set_auth` function"
                         is currently invalid. You need to pass down a schematic object from the
                         `HTTPAuthenticationType` Enum or a type" error will occur.
                         The current schematic passed to this function is: {0}
                         """.format(str(self._request_model.auth_type))
            self.log.error(message)
            raise TypeError(message)

    def _set_body_type_validation(self, type_validation):
        """
        Functionality:
            Pre send validation

            You can apply a validation structure for the Request() data structure.
            This allows you to stop a request from going out if it does not conform to a certain type

        Input:
            @body_type
                A item from the `HTTPRequestType` enum
        """
        self.log.info("""Applying validation the current body content type, The body is {0}"""
                      .format(str(self._request_model.request_type_validation)))
        self._request_model.request_type_validation = type_validation

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
            self.log.error(message)
            raise ValueError(message)

    def _set_body_schematic_validation(self, schematic):
        """
        Functionality:
            Pre send validation
            Test the data object from the Request() object to conform to a certain structure.
            If it does not then the request should not go through.

        Input:
            @body_schematic
                A schematic that will be used for testing against the data object within the Request() object
        """
        self.log.info("""Applying validation to the current body content with a schematic
                                     The schematic is {0}"""
                      .format(str(self._request_model.request_schematic_validation)))
        self._request_model.request_schematic_validation = schematic

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
                             """.format(e)
                self.log.error(message)
                raise e

            except TypeError as e:
                message = """The request was unable to conform to the validation schematic. The
                             schematic applied was {0}
                             The error provided by the schematic validation is {1}
                             To fix this you can either modify the schematic validation or remove it entirely
                             """.format(str(self._request_model.request_schematic_validation), e)
                self.log.error(message)
                raise TypeError(message)

    @staticmethod
    def split_string_into_dict(target, delimiter, sub_delimiter):
        """
        Functionality:
            Split a string into a dictionary the string must follow a list + key value structure
            For example random=test&hello=world or for example random:123|test:123.

        Input:
            @target
                The primary string that should be made into a dictionary
            @delimiter
                The item that will make the string into a list of strings
            @sub_delimiter
                The sub delimiter is used to split the list of strings into a dictionary
        """
        if isinstance(target, str):
            items = (item.split(sub_delimiter) for item in target.split(delimiter))
            try:
                return dict((left.strip(), right.strip()) for left, right in items)
            except ValueError:
                return {}
        return None


class HTTPHelperSessionModel(Model):
    """
        This is the model for the `HTTPHelperSessionHandler` class.
        When using the `HTTPHelperSessionHandler` class there will be the only acceptable values to create state, This
        state can in turn be used within the HTTPHelper class
    """
    mock_enable = BooleanType(required=False, default=False)
    mock_status = IntType(required=False, default=None)
    mock_response = BaseType(required=False, default=None)
    headers = DictType(StringType, default=dict({}))
    auth_data = BaseType(required=False, default=None)
    auth_type = BaseType(required=False, default=None)


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

    _session_model = HTTPHelperSessionModel()
    _authentication_types = [item.value for item in HTTPAuthenticationType]

    def __init__(self, session_model=None):
        self._session_model = HTTPHelperSessionModel(session_model) if session_model is not None \
            else HTTPHelperSessionModel()
        self.log = logging.getLogger('%s.session_handler' % __name__)

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
        session_object.auth_type = self._session_model.auth_type
        session_object.auth_data = self._session_model.auth_data

        return session_object

    def _set_headers(self, headers):
        """
        Functionality:
            Apply a dict object containing values for the headers to the Request() object.

        Input:
            @headers
                A dict object containing the key values for the headers,
        """
        self.log.info("Attempting to set the headers to {0}".format(str(self._session_model.headers)))
        self._session_model.headers = headers

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
            self.log.error(message)
            raise TypeError(message)

    def _set_auth(self, auth_type, auth_data):
        """
        Functionality:
            Apply authentication to the Request() object.
            A type structure and data structure is required to apply a authentication

        Input:
            @auth_schematic
                A value from the `HTTPAuthenticationType` enum
            @auth_details
                Dict containing the information required from the @auth_schematic `HTTPAuthenticationType` enum object

        We need to validate the authentication on apply the value as we need to create the correct auth model from
        the specified values
        """
        self.log.info("Attempting to set the authentication to {0} with the following schematic model {1}"
                      .format(str(auth_data), str(auth_type)))
        self._session_model.auth_data = auth_data
        self._session_model.auth_type = auth_type

    def validate_auth(self):
        """
        Functionality:
            Validate the state of the two auth objects that will be used to apply authentication
            Test if the auth_schematic passed does exist in the HTTPAuthenticationType enum
            We also do a second test to make sure the auth_schematic.value is also a model
        """
        if isinstance(self._session_model.auth_type, Enum) and \
                self._session_model.auth_type.value in self._authentication_types and \
                issubclass(self._session_model.auth_type.value, Model):
            try:
                # Validate the schematic object with the current authentication details
                self._session_model.auth_type.value(self._session_model.auth_data).validate()

                # We need to manually map the supported types to the correct object for the Request() auth
                if self._session_model.auth_type is HTTPAuthenticationType.BasicAuth:
                    HTTPBasicAuth(self._session_model.auth_data.get('username'),
                                  self._session_model.auth_data.get('password'))
                    return True
                else:
                    message = """We are unable to map the enum `HTTPAuthenticationType`
                                 to the request auth object. Please verify if the object exists in the
                                 HTTPAuthenticationType enum and if it does then the mapping for {0}
                                 is missing from the _set_auth function. You need to add a check for
                                 the enum and map the values over to the requests object""" \
                        .format(str(self._session_model.auth_type))
                    self.log.error(message)
                    raise NotImplementedError(message)

            except DataError as e:
                message = """The authentication supplied {0} does not match the required
                             schema {1}. You can view the layout of the schema on the
                             `HTTPAuthenticationType` enum.

                             The error provided by the execution
                             {2}""".format(str(self._session_model.auth_data), str(self._session_model.auth_type), e)
                self.log.error(message)
                raise e

            except TypeError as e:
                message = """The authentication details object passed to this function failed as
                             the type of this object is incorrect. The type passed down was
                             {0} and the expected type is a iterable value that matches the
                             `HTTPAuthenticationType` enum

                             The error provided by the execution
                             {1}""".format(type(self._session_model.auth_data), e)
                self.log.error(message)
                raise TypeError(message)

        else:
            message = """The `auth_schematic` variable passed to the `_set_auth` function"
                         is currently invalid. You need to pass down a schematic object from the
                         `HTTPAuthenticationType` Enum or a type" error will occur.
                         The current schematic passed to this function is: {0}
                         """.format(str(self._session_model.auth_type))
            self.log.error(message)
            raise TypeError(message)


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
    _connection_model = HTTPHelperConnectionModel()

    def __init__(self, connection_model=None):
        self._connection_model = HTTPHelperConnectionModel(connection_model) if connection_model is not None \
            else HTTPHelperConnectionModel()
        self.log = logging.getLogger('%s.connection_handler' % __name__)

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

    def _set_timeout(self, timeout):
        """
        Functionality:
            Apply a timeout to the request structure. This timeout is applied in the send function.

        Input:
            @timeout
                A integer timeout value.
        """
        self.log.info("Attempting to set the timeout to {0} seconds".format(str(timeout)))
        self._connection_model.timeout = timeout

    def validate_timeout(self):
        if isinstance(self._connection_model.timeout, int) or self._connection_model.timeout is None:
            return True

        else:
            message = """The parameters timeout does not contain the correct type.
                         The provided type is {0}. This function only accepts int as a valid timeout""" \
                .format(str(type(self._connection_model.timeout)))
            self.log.error(message)
            raise TypeError(message)

    def _set_retry_policy(self, **kwargs):
        """
        Functionality:
            The retry policy is a one to one mapping of the Retry() object used within the requests class.
            Any of the kwargs mappings inside the Retry can be passed to this function

        Input:
            @kwargs
                A list of defined kwargs items in the Retry() class
        """
        self.log.info("Attempting to Apply a retry policy to the HTTP connection. The retry policy is the"
                      "following {0}".format(str(kwargs)))
        self._connection_model.retry_policy = kwargs

    def validate_retry_policy(self):
        if self._connection_model.retry_policy is None:
            return True

        elif isinstance(self._connection_model.retry_policy, dict):
            Retry(**self._connection_model.retry_policy)
            return True

        return False

    def _set_ssl_verify(self, verify):
        """
        Functionality:
            Define if the request object should look at the SSL verification or ignore it

        Input:
            @verify
                A boolean defining if SSL should be set or not
        """
        self.log.info("Attempting to Apply a SSL Verification to the HTTP connection. The SSL Verification"
                      " being applied is the following {0}".format(str(verify)))
        self._connection_model.ssl_verify = verify

    def validate_ssl_verify(self):
        if isinstance(self._connection_model.ssl_verify, bool):
            return True
        else:
            message = """Unable to set the SSL Verification as the defined parameters is the
                         incorrect type, The type passed to the function is {0} and a int is
                         expected""".format(str(type(self._connection_model.ssl_verify)))
            self.log.error(message)
            raise TypeError(message)

    def _set_proxy(self, proxy):
        """
        Functionality:
            Set the active proxy for the Session() object

        Input:
            @proxy
                requests proxy details
        """
        self.log.info("Attempting to set the proxy details to {0}".format(str(proxy)))
        self._connection_model.proxy = proxy

    def validate_proxy(self):
        if isinstance(self._connection_model.proxy, dict) or self._connection_model.proxy is None:
            return True

        else:
            message = """The proxy provided does not contain the correct type.
                         The provided type is {0}. This function only accepts dict
                         objects this allows a easy mapping to the proxy object as the proxy
                         also exists out of key and value pairs""".format(str(type(self._connection_model.proxy)))
            self.log.error(message)
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
                                 json=session_handler.get_session_model().mock_response)
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
        if request_handler.get_request_model().auth_type is HTTPAuthenticationType.BasicAuth:
            request.auth = HTTPBasicAuth(request_handler.auth_data.get('username'),
                                         request_handler.auth_data.get('password'))

        # Session - HTTPBasicAuth
        if session_handler.get_session_model().auth_type is HTTPAuthenticationType.BasicAuth:
            session.auth = HTTPBasicAuth(session_handler.auth_data.get('username'),
                                         session_handler.auth_data.get('password'))

        response = session.send(request.prepare(), timeout=self._connection_model.timeout)

        return response


class HTTPHelperResponseModel(Model):
    """
        This is the model for the `HTTPHelperResponseHandler` class.
        When using the `HTTPHelperResponseHandler` class there will be the only acceptable values to create state,This
        state can in turn be used within the HTTPHelper class
    """
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

    _response_model = HTTPHelperResponseModel()
    _response_types = [item.value for item in HTTPResponseType]

    def __init__(self, response_model=None):
        self._response_model = HTTPHelperResponseModel(response_model) if response_model is not None \
            else HTTPHelperResponseModel()
        self.log = logging.getLogger('%s.response_handler' % __name__)

    def get_response_model(self):
        """
        Functionality:
            Display the current request model inside this class. This model will be used to create the Request() object
            for the requests library
        """
        return self._response_model

    def validate_response_model(self):
        """
        Functionality:
            We can also run a validation against the model as that model is a schematic
        """
        self._response_model.validate()

    def _set_body_schematic_validation(self, schematic):
        """
        Functionality:
            Set a schematic which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @schematic
                A schematic that is used to test against the response
        """
        self.log.info("Attempting to Apply a body schematic validation on the response with the following"
                      "schematic {0}".format(str(schematic)))
        self._response_model.response_schematic_validation = schematic

    def validate_body_schematic(self, response=None):
        if self._response_model.response_schematic_validation is None:
            return True

        if issubclass(self._response_model.response_schematic_validation, Model) is True:
            try:
                # Decode the response content with the encoding type also given by the response
                decoded_response = response.content.decode(response.encoding)

                # We attempt to decode the response to JSON. To test a schematic you need to have a JSON object to test
                parsed_json = json.loads(decoded_response)

                if isinstance(parsed_json, dict) is False:
                    raise ValueError()

                # The last part to test is does the Parsed JSON match the schematic validation
                self._response_model.response_schematic_validation(parsed_json) \
                    .validate()

                return True

            except DataError as e:
                message = """The response was unable to conform to the validation schematic.
                             The error provided by the schematic validation is {0}
                             To fix this you can either modify the schematic validation or remove it entirely
                             """.format(e)
                self.log.error(message)
                raise e

            except ValueError as e:
                message = """Unable to parse the response as JSON.
                             The response received was {0}.
                             Full error from the JSON parse attempt {1}
                             """.format(str(response.content), e)
                self.log.error(message)
                raise ValueError(message)

        else:
            message = """The proxy schematic does not contain the correct type.
                         The provided type is {0}. The function requires a valid schematic as a argument
                         This allows a response object to be tested against the schematic""" \
                .format(str(type(self._response_model.response_schematic_validation)))
            self.log.error(message)
            raise TypeError(message)

    def _set_status_code_validation(self, status_code):
        """
        Functionality:
            Set a status code which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @status_code
                A integer status code which is used to test against the response status code integer
        """

        self.log.info("Attempting to apply a status code validation on the response with the following"
                      "status code {0}".format(str(status_code)))
        self._response_model.response_status_code_validation = status_code

    def validate_status_code(self, response):
        if self._response_model.response_status_code_validation is None:
            return True

        if isinstance(self._response_model.response_status_code_validation, int):
            if response.status_code != self._response_model.response_status_code_validation:
                message = """The response was unable to conform to the validation status code. The status code
                             applied was {0} The expected status code is {1}
                             To fix this you can either modify the status code validation or remove it entirely
                             """.format(str(response.status_code),
                                        str(self._response_model.response_status_code_validation))
                self.log.error(message)
                raise ValueError(message)

            # If the status code has not been set then we will by default see 400 > as bad responses.
            else:
                return True

        else:
            message = """The proxy schematic does not contain the correct type.
                         The provided type is {0}. The function requires a int to test the response
                         status code against""".format(str(type(self._response_model.response_status_code_validation)))
            self.log.error(message)
            raise TypeError(message)

    def _set_body_type_validation(self, response_type):
        """
        Functionality:
            Set a body type which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @response_type
                A type which is used to test against the response status code integer
                This should be a value from the supported `HTTPResponseType` enum
        """
        self.log.info("Attempting to apply a body type validation on the response with the following"
                      "type {0}".format(str(response_type)))
        self._response_model.response_type_validation = response_type

    def validate_body_type(self, http_response=None):
        if self._response_model.response_type_validation is None:
            return True

        if isinstance(self._response_model.response_type_validation, Enum) and \
                self._response_model.response_type_validation.value in self._response_types:

            # If the type set is JSON. We then attempt to parse it and see if it is valid
            if issubclass(HTTPResponseType.JSON.value, self._response_model.response_type_validation.value):
                try:
                    data = json.loads(http_response.content.decode(http_response.encoding))
                    if isinstance(data, HTTPResponseType.JSON.value) is False:
                        raise ValueError()
                    else:
                        return True

                except ValueError as e:
                    message = """Unable to parse the response as JSON.
                                 The response received was {0}.
                                 Full error from the JSON parse attempt {1}
                                 """.format(str(http_response.content), e)
                    self.log.error(message)
                    raise ValueError(message)

            elif isinstance(self._response_model.response_type_validation.value, type(http_response.content)) is False:
                message = """The response content type does not conform to the validation type. The response
                             type is {0}. The expected type is {1}
                             To fix this you can either modify the type validation or remove it entirely
                             """.format(str(type(http_response.content)),
                                        str(self._response_model.response_type_validation.value))
                self.log.error(message)
                raise TypeError(message)

            else:
                return True

        else:
            message = """The `response_type` argument is the incorrect type. The provided type
                         is {0} and was not found within the `HTTPResponseType` enum. Please make
                         sure that the `response_type` argument is a instance of the HTTPResponseType
                         enum, If not then add the type tot the `HTTPResponseType` enum to allow it
                         """.format(str(type(self._response_model.response_type_validation)))
            self.log.error(message)
            raise TypeError(message)
