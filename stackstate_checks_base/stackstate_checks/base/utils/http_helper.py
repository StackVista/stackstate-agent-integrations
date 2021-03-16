import json
import requests_mock
from enum import Enum
from schematics.models import Model
from schematics.types import StringType
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


class HTTPHelperCommon:
    """
        The HTTP Helper Common class is used for common functionality split between all the other
        HTTP Helper classes.
        Functionality:
            - Mapped enums to lists
            - Log messages
            - Create a dictionary from a string
    """
    _verbose = False

    # Mapped enum values
    http_method_enums = [item.value for item in HTTPMethod]
    request_types = [item.value for item in HTTPRequestType]
    authentication_types = [item.value for item in HTTPAuthenticationType]
    response_types = [item.value for item in HTTPResponseType]

    def __init__(self, verbose=False):
        self._verbose = verbose

    # Print verbose message to track events
    def print_verbose(self, message):
        if self._verbose is True:
            print(message)

    # Below is all the different error types that can be used to print out
    @staticmethod
    def print_error(error):
        raise Exception(error)

    @staticmethod
    def print_not_implemented_error(error):
        raise NotImplementedError(error)

    @staticmethod
    def print_type_error(error):
        raise TypeError(error)

    @staticmethod
    def print_value_error(error):
        raise ValueError(error)

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


class HTTPHelperRequestHandler:
    """
        The HTTP Helper Request Handler is used to control the state of the Request() object within the requests library,
        Anything that can manipulate, create or fetch the state from this Request() object should be contained within,
        Functionality:
            - Create and maintain the Request() object from requests
            - SET && GET HTTP Method
            - SET && GET HTTP Endpoint
            - SET && GET HTTP Query Parameters
            - SET && GET HTTP Body
            - SET && GET HTTP Validation
            - SET && GET HTTP Headers
            - SET && GET HTTP Auth
    """
    _request = Request()
    _common = HTTPHelperCommon()
    _body_schematic_validation = None
    _body_type_validation = None

    # Init the requests objects and common class
    def __init__(self, verbose=False):
        self._request = Request()
        self._common = HTTPHelperCommon(verbose)

    # * The following functions control the Request() object

    # Retrieve the current state of the Request() object
    def get_request(self):
        self._common.print_verbose("Retrieve the active Request() object.")
        return self._request

    # Allows the developer to use a custom request object if required.
    # This opens up some flexibility and control
    def set_request(self, request):
        self._common.print_verbose("Replacing the old Request() object with a user defined one.")
        if isinstance(request, type(Request())):
            self._request = request
        else:
            self._common.print_type_error("""The request object passed to this function is the incorrect type.
                                             The request object must be a instance of the Request() class from the
                                             requests library, Current request object type {0} and object {1}.
                                             To fix this you have to either remove the custom `set_request` function
                                             or inspect the parameter being passed to it"""
                                          .format(type(request), str(request)))

    # This will reset the state of the Request() object and replace it with a new one
    def reset_request(self):
        self._common.print_verbose("Creating a new Request() object and replacing the old one.")
        self._request = Request()

    # * The following functions control the HTTP Method applied to the Requests object for example
    #   GET, POST

    # Clear the current state of the HTTP Method applied to the Request() object
    def clear_method(self):
        self._common.print_verbose("Clearing the HTTP Method.")
        self._request.method = None

    # Retrieve the current state of the HTTP Method applied to the Request() object
    def get_method(self):
        self._common.print_verbose("Retrieve the Request() object HTTP Method.")
        return self._request.method

    def set_method(self, method):
        """
        Functionality:
            Set the current HTTP Method for the Requests() object from the HTTPMethod enum
            If a method is specified which does not exist in the HTTPMethod a `Not Implemented` error will be triggered.

        Input:
            @method
                This can either be a value from the `HTTPMethod` or a direct string that can be mapped to the `HTTPMethod`
                The value of this will be the type of request made for example POST or GET
        """

        self._common.print_verbose("Attempting to set the active http method to {0}".format(str(method)))

        # ENUM Check
        # We attempt to see if the provided variable exists inside the enum
        # The following checks are made
        # - Is the method a enum value
        # - Does the method exist in the enum
        # - Can we get the value data from the method
        if isinstance(method, Enum) and \
                hasattr(method, "value") and \
                method.value in self._common.http_method_enums:
            self._common.print_verbose("Enum Method found inside the `HTTPMethod` enum, Applying {0} as the active"
                                       "method."
                                       .format(str(method.value)))
            self._request.method = method.value

        # String Check
        # If the value was not found in a enum then we attempt to find the enum that contains the same as the
        # string value provided.
        # The following checks are made
        # - Is the method passed a string so that we can match it in the enum
        # - Does that string exist in the mapped enum list.
        elif isinstance(method, str) and method in self._common.http_method_enums:
            self._common.print_verbose("String method found inside the `HTTPMethod` enum, Applying {0} as the active"
                                       "method."
                                       .format(str(method)))
            self._request.method = method

        # If we do not find the value inside the enum then it means that we do not support the method yet
        else:
            self._common.print_not_implemented_error("""Unable to find the provided {0} method. Currently the code
                                                       block only supports the methods provided in the `HTTPMethod`
                                                       Enum. If you would like to add another method feel free to add it
                                                       within the `HTTPMethod` Enum or change the supplied {1} to a
                                                       supported type""".format(str(method), str(method)))

    # * The following functions control the HTTP Endpoint and Endpoint creation
    #   For example http://www.example.com and http://www.example.com?test=123 will both be mapped to the correct
    #   values within the Request() object

    # Clear the current state of the HTTP URL applied to the Request() object
    def clear_url(self):
        self._common.print_verbose("Clearing the HTTP URL.")
        self._request.url = None

    # Retrieve the value of the current Endpoint on the Request() object
    def get_url(self):
        self._common.print_verbose("Retrieving current HTTP Endpoint")
        return self._request.url

    def set_url(self, url):
        """
        Functionality:
            The Request() endpoint is set with this function.
            Some extra functionality is build-into this function to analyze a URL. When something like the following is
            passed to the function 'http://www.url.com?test=123' the query parameters on this URL will be split out and
            applied into the correct object within the Request() object

        Input:
            @url
                A string object containing the endpoint that should be queried
        """

        self._common.print_verbose("Attempting to set the active current url to {0}".format(str(url)))

        # We need a string to be able to set a URL endpoint, Anything else is unsupported
        if isinstance(url, str):
            # We deconstruct the URL at this point.
            # This allows us to piece it back together with only what we need.
            parsed_url = urlparse.urlparse(url)
            self._common.print_verbose("Endpoint parsed successfully, Result is as follow {0}".format(str(parsed_url)))

            # The URL is recreated here by adding the schema, net location and path together
            url = (parsed_url.scheme + "://" if len(parsed_url.scheme) > 0 else "") \
                + parsed_url.netloc \
                + parsed_url.path
            self._common.print_verbose("Reconstructed URL {0}".format(str(url)))

            # Apply the reconstructed Endpoint to the Request() object
            self._request.url = url

            # If we found any extra data within the URL we then attempt to map it to the correct location
            if parsed_url.query is not None and len(parsed_url.query) > 0:
                query_dict = self._common.split_string_into_dict(parsed_url.query, "&", "=")
                # Apply the extracted parameters into the Request() object
                self.set_query_param(query_dict)

        # Invalid URL
        else:
            self._common.print_type_error("""The URL provided is incorrect, The type provided is {0} adn the value is
                                         {1} .The URL needs to be parsed thus we need a string to be able to parse
                                         the URL""".format(str(type(url)), str(url)))

    # * The following functions control the HTTP Query parameters
    #   It can be set, cleared or retrieved

    # Retrieve the value of the current Query Parameters on the Request() object
    def get_query_param(self):
        self._common.print_verbose("Retrieving current HTTP Query Parameters from the Request() object")
        return self._request.params

    # Reset the value of the current Query Parameters on the Request() object
    def clear_query_param(self):
        self._common.print_verbose("Setting the HTTP Query Parameters object to a empty {} on the Request() object")
        self._request.params = None

    def set_query_param(self, parameters):
        """
        Functionality:
            This function controls the state of the HTTP Query Parameters object.

        Input:
            @parameters
                A basic dict object mapping values to keys
        """

        self._common.print_verbose("Attempting to set the active query parameters to {0}".format(str(parameters)))

        # If a valid dict was passed then we can successfully apply the object as the Request() object is expecting the
        # same results.
        if isinstance(parameters, dict):
            self._request.params = parameters

        else:
            self._common.print_type_error("""The parameters provided does not contain the correct type.
                                         The provided type is {0}. This function only accepts dict
                                         objects this allows a easy mapping to the query object as the parameters
                                         also exists out of key and value pairs.
                                         To fix this please look at the {1} object or remove the query parameters"""
                                          .format(str(type(parameters)), str(parameters)))

    # * The following functions control the body that's being send the the HTTP Endpoint.

    # Retrieve the value of the current Data Parameters on the Request() object
    def get_body(self):
        self._common.print_verbose("Retrieving current HTTP Data Parameters from the Request() object")
        return self._request.data

    # Reset the value of the current Query Parameters on the Request() object
    def clear_body(self):
        self._common.print_verbose("Clear current HTTP Data Parameters from the Request() object")
        self._request.data = []

    def set_body(self, body):
        """
        Functionality:
            Apply a body to the Request() object.
            We do not restrict the body type as you may wish to send something other than a JSON object

        Input:
            @body
                A body containing any data you want to send to the HTTP Endpoint
        """
        self._common.print_verbose("Attempting to set the active data object to {0}".format(str(body)))
        self._request.data = body

    # * The following functions control the HTTP Headers passed to the Request() object.

    # Retrieve the value of the current Headers on the Request() object
    def get_headers(self):
        self._common.print_verbose("Retrieving current HTTP Headers from the Request() object")
        return self._request.headers

    # Reset the value of the current Headers on the Request() object
    def clear_headers(self):
        self._common.print_verbose("Clearing the active HTTP Headers from the Request() object")
        self._request.headers = {}

    def set_headers(self, headers):
        """
        Functionality:
            Apply a dict object containing values for the headers to the Request() object.

        Input:
            @headers
                A dict object containing the key values for the headers,
        """
        self._common.print_verbose("Attempting to set the headers to {0}".format(str(headers)))

        # We only accept the headers if it is a dictionary
        if isinstance(headers, dict):
            self._request.headers = headers
        else:
            self._common.print_type_error("""The headers provided does not contain the correct type.
                                         The provided type is {0}. This function only accepts dict
                                         objects this allows a easy mapping to the query object as the headers
                                         also exists out of key and value pairs. The current headers passed
                                         was the following {1}""".format(str(type(headers)), str(headers)))

    # * The following functions control the HTTP Authentication passed to the Request() object.

    # Retrieve the value of the current Authentication on the Request() object
    def get_auth(self):
        self._common.print_verbose("Retrieving current Authentication from the Request() object")
        return self._request.auth

    # Reset the value of the current Authentication on the Request() object
    def clear_auth(self):
        self._common.print_verbose("Clearing the active Authentication from the Request() object")
        self._request.auth = None

    def set_auth(self, auth_schematic, auth_details):
        """
        Functionality:
            Apply authentication to the Request() object.
            A type structure and data structure is required to apply a authentication

        Input:
            @auth_schematic
                A value from the `HTTPAuthenticationType` enum
            @auth_details
                Dict containing the information required from the @auth_schematic `HTTPAuthenticationType` enum object
        """

        self._common.print_verbose("Attempting to set the authentication to {0} with the following schematic model {1}"
                                   .format(str(auth_details), str(auth_details)))

        # Test if the auth_schematic passed does exist in the HTTPAuthenticationType enum
        # We also do a second test to make sure the auth_schematic.value is also a model
        if isinstance(auth_schematic, Enum) and \
                auth_schematic.value in self._common.authentication_types and \
                issubclass(auth_schematic.value, Model):
            try:
                # Validate the schematic object with the current authentication details
                auth_schematic.value(auth_details).validate()

                # We need to manually map the supported types to the correct object for the Request() auth
                if auth_schematic is HTTPAuthenticationType.BasicAuth:
                    self._request.auth = HTTPBasicAuth(auth_details.get('username'), auth_details.get('password'))
                else:
                    self._common.print_not_implemented_error("""We are unable to map the enum `HTTPAuthenticationType`
                                                   to the request auth object. Please verify if the object exists in the
                                                   HTTPAuthenticationType enum and if it does then the mapping for {0}
                                                   is missing from the set_auth function. You need to add a check for
                                                   the enum and map the values over to the requests object"""
                                                             .format(str(auth_schematic)))

            except DataError as e:
                self._common.print_type_error("""The authentication supplied {0} does not match the required
                                                schema {1}. You can view the layout of the schema on the
                                                `HTTPAuthenticationType` enum.

                                                The error provided by the execution
                                                {2}"""
                                              .format(str(auth_details), str(auth_schematic), e))
            except TypeError as e:
                self._common.print_type_error("""The authentication details object passed to this function failed as
                                                the type of this object is incorrect. The type passed down was
                                                {0} and the expected type is a iterable value that matches the
                                                `HTTPAuthenticationType` enum

                                                The error provided by the execution
                                                {1}"""
                                              .format(type(auth_details), e))

        else:
            self._common.print_type_error("""The `auth_schematic` variable passed to the `set_auth` function"
                                            is currently invalid. You need to pass down a schematic object from the
                                            `HTTPAuthenticationType` Enum or a type" error will occur.
                                            The current schematic passed to this function is: {0}
                                            """.format(str(auth_schematic)))

    # * The following functions control the custom validation on the Request() data object.

    # Get the body type validation from the Request() data object
    def get_body_type_validation(self):
        return self._body_type_validation

    # Remove the body type validation from the Request() data object
    def remove_body_type_validation(self):
        self._common.print_verbose("""Removing the body type validation""")
        self._body_type_validation = None

    def set_body_type_validation(self, body_type):
        """
        Functionality:
            Pre send validation

            You can apply a validation structure for the Request() data structure.
            This allows you to stop a request from going out if it does not conform to a certain type

        Input:
            @body_type
                A item from the `HTTPRequestType` enum
        """

        self._common.print_verbose("""Applying validation the current body content type, The body is {0}"""
                                   .format(str(self._request.data)))

        # Validate that the `body_type` parameter is a instance of the `HTTPRequestType` enum
        if isinstance(body_type, Enum) and \
                hasattr(body_type, "value") and \
                body_type.value in self._common.request_types:
            # Save the validation to test against later
            self._body_type_validation = body_type
            self._common.print_verbose("""The body is valid and matched either the defined {0}
                                      type or is empty."""
                                       .format(str(body_type)))

        else:
            self._common.print_type_error("""The body does not conform to the body type provided ({0}).
                                         Either the body type passed to the `validate_body` function needs to be
                                         changed, The validation needs to be removed to allow this body type or
                                         the body needs to be looked at and why it is passing down the incorrect data.
                                         The current body tested content is {1}
                                         """.format(str(body_type),
                                                    self._request.data))

    # Get the body type schematic validation from the Request() data object
    def get_body_schematic_validation(self):
        return self._body_schematic_validation

    # Remove the body schematic validation from the Request() data object
    def remove_body_schematic_validation(self):
        self._common.print_verbose("""Removing the body schematic validation""")
        self._body_schematic_validation = None

    def set_body_schematic_validation(self, body_schematic):
        """
        Functionality:
            Pre send validation
            Test the data object from the Request() object to conform to a certain structure.
            If it does not then the request should not go through.

        Input:
            @body_schematic
                A schematic that will be used for testing against the data object within the Request() object
        """

        self._common.print_verbose("""Applying validation to the current body content with a schematic
                                     The schematic is {0}""".format(str(body_schematic)))

        # Attempt to check the type from body_schematic to verify if we can use it to verify against
        try:
            if issubclass(body_schematic, Model) is True:
                self._body_schematic_validation = body_schematic
            else:
                raise TypeError

        except TypeError as e:
            self._common.print_type_error("""The `body_schematic` variable passed to the `validate_body_structure`"
                                            is currently invalid. You need to pass down a schematic object or a type"
                                            error will occur. The current schematic passed to this function is: {0}

                                            The error provided by the python execution
                                            {1}
                                            """.format(str(body_schematic), e))

    def validate(self):
        self._common.print_verbose("Attempting to validate the request structure.")

        # If the HTTP Response Validation Schematic has been set
        if self._body_schematic_validation is not None:
            try:
                # The last part to test is does the Parsed JSON match the schematic validation
                self._body_schematic_validation(self._request.data) \
                    .validate()

            except DataError as e:
                self._common.print_type_error("""The request was unable to conform to the validation schematic. The
                                schematic applied was {0}
                                The error provided by the schematic validation is {1}
                                To fix this you can either modify the schematic validation or remove it entirely
                                """.format(str(self._body_schematic_validation), e))

            except TypeError as e:
                self._common.print_type_error("""The request was unable to conform to the validation schematic. The
                                schematic applied was {0}
                                The error provided by the schematic validation is {1}
                                To fix this you can either modify the schematic validation or remove it entirely
                                """.format(str(self._body_schematic_validation), e))

        # Test the type of the request body
        if self._body_type_validation is not None and \
                isinstance(type(self._request.data), type(self._body_type_validation.value)) is False:
            self._common.print_type_error("""The request was unable to conform to the type validation. The
                            body type applied was {0} where the expected type is {1}
                            To fix this you can either modify the type validation or remove it entirely
                            """.format(str(type(self._request.data)), str(type(self._body_type_validation.value))))


class HTTPHelperSessionHandler:
    """
        The HTTP Helper Session Handler is used to control the state of the Session() object within the requests library,
        Anything that can manipulate, create or fetch the state from this Session() object should be contained within,
        Functionality:
            - Create and maintain the Session() object from requests
            - SET Mount Adaptor for unit testing
            - SET && GET HTTP Query Parameters
            - SET && GET HTTP Headers
            - SET && GET HTTP Auth
    """

    _session = Session()
    _common = HTTPHelperCommon()

    # Init the session object and common class
    def __init__(self, verbose=False):
        self._session = Session()
        self._common = HTTPHelperCommon(verbose)

    # * The following functions control the Session() object

    # Retrieve the current state of the Session() object
    def get_session(self):
        self._common.print_verbose("Retrieve the active Session() object.")
        return self._session

    # Allows the developer to use a custom session object if required.
    # This opens up some flexibility and control
    def set_session(self, session):
        self._common.print_verbose("Replacing the old Session() object with a user defined one.")

        if isinstance(session, type(Session())):
            self._session = session
        else:
            self._common.print_type_error("""The request object passed to this function is the incorrect type.
                                             The session object must be a instance of the Session() class from the
                                             requests library, Current request session type {0} and object {1}"""
                                          .format(type(session), str(session)))

    # This will reset the state of the Session() object and replace it with a new one
    def reset_session(self):
        self._common.print_verbose("Creating a new Session() object and replacing the old one.")
        self._session = Session()

    # Unit Testing - Apply a adapter to the current session object
    def mount_adapter(self, adapter):
        self._session.mount('mock://', adapter)

    # * The following functions control the query parameters on the Session() data object.

    # Clear the current query parameters object on the Session() object
    def clear_query_param(self):
        self._common.print_verbose("Clearing the query parameters on the Session() object.")
        self._session.params.clear()

    # Retrieve the current query parameters object from the Session() object
    def get_query_param(self):
        self._common.print_verbose("Retrieving the query parameters on the Session() object.")
        return self._session.params

    def set_query_param(self, parameters):
        """
        TODO:
        Functionality:
            Lorem Ipsum

        Input:
            @parameters
                Lorem Ipsum
        """

        self._common.print_verbose("""Applying the following query parameters object to the Session() object {0}"""
                                   .format(str(parameters)))

        # The object must be a dict to be able to map key value pairs to the query parameters
        if isinstance(parameters, dict):
            self._session.params.update(parameters)
        else:
            self._common.print_type_error("""The parameters provided does not contain the correct type.
                                            The provided type is {0}. This function only accepts dict objects this
                                            allows a easy mapping to the query object as the also exists out of
                                            key and value objects. Attempting to apply the following parameters {1}
                                            """.format(str(type(parameters)), str(parameters)))

    # * The following functions controls the headers on the Session() data object.

    # Clear the current headers on the Session() object
    def clear_headers(self):
        self._common.print_verbose("Clearing the headers on the Session() object.")
        self._session.headers.clear()

    # Retrieve the current headers object from the Session() object
    def get_headers(self):
        self._common.print_verbose("Retrieving the headers on the Session() object.")
        return self._session.headers

    def set_headers(self, headers):
        """
        Functionality:
            Apply a headers dict object to the Session() object

        Input:
            @headers
                Must be a dict containing key value header pairs
        """

        self._common.print_verbose("""Applying the following headers object to the Session() object {0}"""
                                   .format(str(headers)))

        # The object must be a dict to be able to map key value pairs to the headers
        if isinstance(headers, dict):
            self._session.headers.update(headers)
        else:
            self._common.print_type_error("""The parameters provided does not contain the correct type.
                                            The provided type is {0}. This function only accepts dict objects this
                                            allows a easy mapping to the headers object as the also exists out of
                                            key and value objects. Attempting to apply the following headers {1}
                                            """.format(str(type(headers)), str(headers)))

    # * The following functions controls the authentication on the Session() data object.

    # Clear the current authentication method on the Session() object
    def clear_auth(self):
        self._common.print_verbose("Clearing the authentication method on the Session() object.")
        self._session.auth = None

    # Retrieve the current authentication method from the Session() object
    def get_auth(self):
        self._common.print_verbose("Retrieving the authentication method on the Session() object.")
        return self._session.auth

    def set_auth(self, auth_schematic, auth_details):
        """
        Functionality:
            Apply a authentication models to the current Session() object.
            The model is applied by specifying a Enum that defines the authentication structure, A second parameter is then
            provided which maps the data structure into the proper requests authentication model.

        Input:
            @auth_schematic
                A object from the `HTTPAuthenticationType`.
            @auth_details
                The authentication details dict object. This object will be tested against the `HTTPAuthenticationType`
                enum to make sure the data mapping can be mapped to the enum.
        """

        self._common.print_verbose("Attempting to set the authentication to {0} with the following schematic model {1}"
                                   .format(str(auth_details), str(auth_details)))

        # Test if the auth_schematic passed does exist in the HTTPAuthenticationType enum
        # We also do a second test to make sure the auth_schematic.value is also a model
        if isinstance(auth_schematic, Enum) and \
                auth_schematic.value in self._common.authentication_types and \
                issubclass(auth_schematic.value, Model):
            try:
                # Validate the schematic object with the current authentication details
                auth_schematic.value(auth_details).validate()

                # We need to manually map the supported types to the correct object for the Request() auth
                if auth_schematic is HTTPAuthenticationType.BasicAuth:
                    self._session.auth = HTTPBasicAuth(auth_details.get('username'), auth_details.get('password'))
                else:
                    self._common.print_not_implemented_error("""We are unable to map the enum `HTTPAuthenticationType`
                                                   to the request auth object. Please verify if the object exists in the
                                                   HTTPAuthenticationType enum and if it does then the mapping for {0}
                                                   is missing from the set_auth function. You need to add a check for
                                                   the enum and map the values over to the requests object"""
                                                             .format(str(auth_schematic)))

            except DataError as e:
                self._common.print_type_error("""The authentication supplied {0} does not match the required
                                                schema {1}. You can view the layout of the schema on the
                                                `HTTPAuthenticationType` enum.

                                                The error provided by the execution
                                                {2}"""
                                              .format(str(auth_details), str(auth_schematic), e))
            except TypeError as e:
                self._common.print_type_error("""The authentication details object passed to this function failed as
                                                the type of this object is incorrect. The type passed down was
                                                {0} and the expected type is a iterable value that matches the
                                                `HTTPAuthenticationType` enum

                                                The error provided by the execution
                                                {1}"""
                                              .format(type(auth_details), e))

        else:
            self._common.print_type_error("""The `auth_schematic` variable passed to the `set_auth` function"
                                            is currently invalid. You need to pass down a schematic object from the
                                            `HTTPAuthenticationType` Enum or a type" error will occur.
                                            The current schematic passed to this function is: {0}
                                            """.format(str(auth_schematic)))

    def apply_mock(self, method, url, status_code=None, response=None):
        adapter = requests_mock.Adapter()
        self.mount_adapter(adapter)
        adapter.register_uri(method, url,
                             status_code=status_code,
                             json=response)


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
    _common = HTTPHelperCommon()
    _verbose = False
    _timeout = None
    _proxy = None
    _retry_policy = None
    _ssl_verify = True

    def __init__(self, verbose=False):
        self._verbose = verbose

    # * The following functions controls the timeout on the request.

    # Get the current timeout set
    def get_timeout(self):
        self._common.print_verbose("Retrieving the timeout on the connection.")
        return self._timeout

    # Remove the active timeout
    def clear_timeout(self):
        self._common.print_verbose("Clearing the timeout on the connection.")
        self._timeout = None

    def set_timeout(self, timeout):
        """
        Functionality:
            Apply a timeout to the request structure. This timeout is applied in the send function.

        Input:
            @timeout
                A integer timeout value.
        """
        self._common.print_verbose("Attempting to set the timeout to {0} seconds"
                                   .format(str(timeout)))

        if isinstance(timeout, int):
            self._timeout = timeout

        else:
            self._common.print_type_error("""The parameters timeout does not contain the correct type.
                                         The provided type is {0}. This function only accepts int as a valid timeout"""
                                          .format(str(type(timeout))))

    # * The following functions controls the retry policy on the request.

    # Get the current retry policy set
    def get_retry_policy(self):
        self._common.print_verbose("Retrieving the retry policy on the connection.")
        return self._retry_policy

    # Remove the retry policy timeout
    def clear_retry_policy(self):
        self._common.print_verbose("Clearing the retry policy on the connection.")
        self._retry_policy = None

    def set_retry_policy(self, **kwargs):
        """
        Functionality:
            The retry policy is a one to one mapping of the Retry() object used within the requests class.
            Any of the kwargs mappings inside the Retry can be passed to this function

        Input:
            @kwargs
                A list of defined kwargs items in the Retry() class
        """
        self._common.print_verbose("Attempting to Apply a retry policy to the HTTP connection. The retry policy is the"
                                   "following {0}"
                                   .format(str(kwargs)))

        self._retry_policy = Retry(**kwargs)

    # * The following functions controls the SSL Verification on the request.

    # Restore the state of the SSL Verify
    def clear_ssl_verify(self):
        self._common.print_verbose("Clearing the SSL Verification on the connection.")
        self._ssl_verify = True

    # Retrieve the current state of the SSL verification
    def get_ssl_verify(self):
        self._common.print_verbose("Retrieving the SSL Verification on the connection.")
        return self._ssl_verify

    def set_ssl_verify(self, verify):
        """
        Functionality:
            Define if the request object should look at the SSL verification or ignore it

        Input:
            @verify
                A boolean defining if SSL should be set or not
        """

        self._common.print_verbose("Attempting to Apply a SSL Verification to the HTTP connection. The SSL Verification"
                                   " being applied is the following {0}"
                                   .format(str(verify)))

        if isinstance(verify, bool):
            self._ssl_verify = verify
        else:
            self._common.print_type_error("""Unable to set the SSL Verification as the defined parameters is the
                                            incorrect type, The type passed to the function is {0} and a int is
                                            expected"""
                                          .format(str(type(verify))))

    # * The following functions controls the proxy on the Session() data object.

    def clear_proxy(self):
        self._common.print_verbose("Clearing the proxy settings on the Session() object.")
        self._proxy = None

    def get_proxy(self):
        self._common.print_verbose("Retrieving the proxy settings on the Session() object.")
        return self._proxy

    def set_proxy(self, proxy):
        """
        Functionality:
            Set the active proxy for the Session() object

        Input:
            @proxy
                requests proxy details
        """

        self._common.print_verbose("Attempting to set the proxy details to {0}"
                                   .format(str(proxy)))

        # The dict object needs to match the requests dict proxy object
        if isinstance(proxy, dict):
            self._proxy = proxy
        else:
            self._common.print_type_error("""The proxy provided does not contain the correct type.
                                         The provided type is {0}. This function only accepts dict
                                         objects this allows a easy mapping to the proxy object as the proxy
                                         also exists out of key and value pairs""".format(str(type(proxy))))

    # * The following functions controls the sending of the request.

    def send(self, session_handler, request_handler, response_handler):
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
            @response_handler
                The Response Handler Class. This allows the user to also pass down a custom response handler if required
        """

        self._common.print_verbose("Sending the HTTP request.")\

        request_object = request_handler.get_request()
        session_object = session_handler.get_session()

        # Apply the retry policy if defined
        if self._retry_policy is not None:
            adapter = HTTPAdapter(max_retries=self._retry_policy)
            session_object.mount("https://", adapter)
            session_object.mount("http://", adapter)

        # Apply the proxy details
        # If non is found then it is cleared from the object
        if self._proxy is None:
            self.clear_proxy()
        else:
            self.set_proxy(self._proxy)

        # Apply the SSL verification
        session_object.verify = self._ssl_verify

        # Request validation
        request_handler.validate()

        # Apply the timeout to the Session() send
        # Send the request out
        response = session_object.send(
            request_object.prepare(),
            timeout=self._timeout
        )

        self._common.print_verbose("Response: {0}".format(str(response)))

        # Validate the response to determine if there was any errors
        validation_errors = response_handler.validate(response)

        self._common.print_verbose("Validation Errors: {0}".format(str(validation_errors)))

        # If any errors occurred, We map the response to still be accessible but also pass down the errors
        if len(validation_errors) > 0:
            return {
                "valid": False,
                "errors": validation_errors,
                "response": response
            }

        # Else return valid structure
        return {
            "valid": True,
            "response": response
        }


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

    _common = HTTPHelperCommon()
    _validate_schematic = None
    _validate_status_code = None
    _validate_type = None

    def __init__(self, verbose=False):
        self._common = HTTPHelperCommon(verbose)

    # Remove the response body validation
    def clear_body_schematic_validation(self):
        self._common.print_verbose("Clearing the body schematic validation on the response.")
        self._validate_schematic = None

    # Retrieve the current response body validation
    def get_body_schematic_validation(self):
        self._common.print_verbose("Retrieving the body schematic validation on the response.")
        return self._validate_schematic

    def set_body_schematic_validation(self, schematic):
        """
        Functionality:
            Set a schematic which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @schematic
                A schematic that is used to test against the response
        """

        self._common.print_verbose("Attempting to Apply a body schematic validation on the response with the following"
                                   "schematic {0}"
                                   .format(str(schematic)))

        if issubclass(schematic, Model) is True:
            self._validate_schematic = schematic

        else:
            self._common.print_type_error("""The proxy schematic does not contain the correct type.
                                         The provided type is {0}. The function requires a valid schematic as a argument
                                         This allows a response object to be tested against the schematic"""
                                          .format(str(type(schematic))))

    # Clear the status code validation on the response object
    def clear_status_code_validation(self):
        self._common.print_verbose("Retrieving the status code validation on the response.")
        self._validate_status_code = None

    # Retrieve the status code validation on the response object
    def get_status_code_validation(self):
        self._common.print_verbose("Retrieving the status code validation on the response.")
        return self._validate_status_code

    def set_status_code_validation(self, status_code):
        """
        Functionality:
            Set a status code which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @status_code
                A integer status code which is used to test against the response status code integer
        """

        self._common.print_verbose("Attempting to apply a status code validation on the response with the following"
                                   "status code {0}"
                                   .format(str(status_code)))

        if isinstance(status_code, int):
            self._validate_status_code = status_code

        else:
            self._common.print_type_error("""The proxy schematic does not contain the correct type.
                                         The provided type is {0}. The function requires a int to test the response
                                         status code against"""
                                          .format(str(type(status_code))))

    # Clear the body type validation on the response object
    def clear_body_type_validation(self):
        self._common.print_verbose("Clear the body type validation on the response.")
        self._validate_type = None

    # Retrieve the body type validation on the response object
    def get_body_type_validation(self):
        self._common.print_verbose("Retrieving the body type validation on the response.")
        return self._validate_type

    def set_body_type_validation(self, response_type):
        """
        Functionality:
            Set a body type which will be used to test against the response. This can force a error message when the
            response is analyzed

        Input:
            @response_type
                A type which is used to test against the response status code integer
                This should be a value from the supported `HTTPResponseType` enum
        """

        self._common.print_verbose("Attempting to apply a body type validation on the response with the following"
                                   "type {0}"
                                   .format(str(response_type)))

        if isinstance(response_type, Enum) and \
                response_type.value in self._common.response_types:
            self._validate_type = response_type

        else:
            self._common.print_type_error("""The `response_type` argument is the incorrect type. The provided type
                                            is {0} and was not found within the `HTTPResponseType` enum. Please make
                                            sure that the `response_type` argument is a instance of the HTTPResponseType
                                            enum, If not then add the type tot the `HTTPResponseType` enum to allow it
                                            """
                                          .format(str(type(response_type))))

    def validate(self, response):
        """
        Functionality:
            This function brings together all the validation structures for the response.
            Those validation is then executed and a list of errors are compiled.
            The response will then return a list of errors to the developer

        Input:
            @response
                The response object from the HTTP Request
        """

        self._common.print_verbose("Attempting to validate the response.")

        errors = list([])

        # If the HTTP Response Validation Schematic has been set
        if self._validate_schematic is not None:
            try:
                # Decode the response content with the encoding type also given by the response
                decoded_response = response.content.decode(response.encoding)

                # We attempt to decode the response to JSON. To test a schematic you need to have a JSON object to test
                parsed_json = json.loads(decoded_response)

                if isinstance(parsed_json, dict) is False:
                    raise ValueError()

                # The last part to test is does the Parsed JSON match the schematic validation
                self._validate_schematic(parsed_json) \
                    .validate()

            except DataError as e:
                errors.append("""The response was unable to conform to the validation schematic. The schematic
                                applied was {0}
                                The error provided by the schematic validation is {1}
                                To fix this you can either modify the schematic validation or remove it entirely
                                """.format(str(self._validate_schematic), e))

            except ValueError as e:
                errors.append("""Unable to parse the response as JSON.
                                 The response received was {0}.
                                 Full error from the JSON parse attempt {1}
                                 """.format(str(response.content), e))

        # If the HTTP Response Validation Status Code has been set
        if self._validate_status_code is not None and response.status_code != self._validate_status_code:
            errors.append("""The response was unable to conform to the validation status code. The status code
                             applied was {0}
                             The expected status code is {1}
                             To fix this you can either modify the status code validation or remove it entirely
                             """.format(str(response.status_code), str(self._validate_status_code)))
        # If the status code has not been set then we will by default see 400 > as bad responses.
        elif response.status_code >= 400:
            errors.append("""Server responded with a {0}""".format(str(response.status_code)))

        # If the HTTP Response Type has been set
        # Test if the HTTP Response Type is a enum of type HTTPResponseType
        if self._validate_type is not None and \
                type(self._validate_type) is HTTPResponseType and \
                isinstance(self._validate_type, Enum) is True:

            # If the type set is JSON. We then attempt to parse it and see if it is valid
            if self._validate_type is HTTPResponseType.JSON:
                try:
                    data = json.loads(response.content.decode(response.encoding))
                    if isinstance(data, dict) is False:
                        raise ValueError()

                except ValueError as e:
                    errors.append("""Unable to parse the response as JSON.
                                     The response received was {0}.
                                     Full error from the JSON parse attempt {1}
                                     """.format(str(response.content), e))

            elif isinstance(self._validate_type.value, type(response.content)) is False:
                errors.append("""The response content type does not conform to the validation type. The response
                                 type is {0}.
                                 The expected type is {1}
                                 To fix this you can either modify the type validation or remove it entirely
                                 """.format(str(type(response.content)), str(self._validate_type.value)))

        # Return all the errors that occurred
        return errors


class HTTPHelper:
    """
        The HTTP Helper Handler is used to create compact methods using most of the function defined in the
        Connection, Request, Session and Response Helpers
        Functionality:
            - Overwrite Connection Helper
            - Overwrite Request Helper
            - Overwrite Session Helper
            - Overwrite Response Helper
            - GET Request
            - POST Request
            - DELETE Request
            - PATCH Request
            - PUT Request

        There is 3 ways to approach creating a HTTP Helper
        - The developer can create the HTTPHelperRequestHandler, HTTPHelperSessionHandler, HTTPHelperResponseHandler and
          HTTPHelperConnectionHandler.
          These can then manually be passed down as kwargs to the send function
        - The developer can create the HTTPHelperRequestHandler, HTTPHelperSessionHandler, HTTPHelperResponseHandler and
          HTTPHelperConnectionHandler.
          These can then manually be set within the HTTPHelper class with the overwrite functions
        - Or it can be left to the internal state where the Helper control and build the state.
          Thus if the developer use the setters and getter those internal state will be manipulated
    """

    _common = HTTPHelperCommon()

    def __init__(self, verbose=False):
        self._common = HTTPHelperCommon(verbose)

    @staticmethod
    def _builder(active_method, **kwargs):
        """
        Functionality:
            A generic builder to contains most of the functionality on the Connection, Request, Session and Response Helpers
            This function will be used by compact methods to build up a request

        Input:
            @active_method
                The active HTTP method for example GET or POST
            @kwargs
                This parameters is another way to define object values outside of the Helper classes.
                Accepted Values:
                    - mock                              (Boolean) Enable or Disable the mock requests
                    - mock_status                       (Integer) The mock response status code
                    - mock_response                     (Any) The mock response object
                    - url                               (String) Set the endpoint
                    - body                              (Any) The request body structure
                    - headers                           (Dict) The request headers object
                    - query                             (Dict) The request query parameters object
                    - request_schematic_validation      (Schematic) The request body schematic validation
                    - request_type_validation           (Any Type) The request body type validation
                    - response_status_code_validation   (Integer) The response status code validation
                    - response_type_validation          (Any Type) The response type validation
                    - response_schematic_validation     (Schematic) The response body schematic validation
                    - timeout                           (Integer) The connection timeout
                    - ssl_verify                        (Boolean) Test if the request should be SSL
                    - retry_policy                      (Retry() object kwargs) Create a retry policy for the HTTP request
        """
        connection = HTTPHelperConnectionHandler()
        session = HTTPHelperSessionHandler()
        request = HTTPHelperRequestHandler()
        response = HTTPHelperResponseHandler()

        if kwargs.get("mock") is True:
            adapter = requests_mock.Adapter()
            session.mount_adapter(adapter)
            adapter.register_uri(active_method.value,
                                 kwargs.get("url"),
                                 status_code=kwargs.get("mock_status", None),
                                 json=kwargs.get("mock_response", None))

        def apply_if_kwarg_exists(function, kwarg):
            if kwarg is not None:
                function(kwarg)

        # At the end we apply kwarg variables to allow last second overrides
        apply_if_kwarg_exists(request.set_url, kwargs.get("url"))
        apply_if_kwarg_exists(request.set_method, active_method.value)
        apply_if_kwarg_exists(request.set_body, kwargs.get("body"))
        apply_if_kwarg_exists(request.set_headers, kwargs.get("headers"))
        apply_if_kwarg_exists(request.set_query_param, kwargs.get("query"))
        apply_if_kwarg_exists(request.set_body_schematic_validation, kwargs.get("request_schematic_validation"))
        apply_if_kwarg_exists(request.set_body_type_validation, kwargs.get("request_type_validation"))
        apply_if_kwarg_exists(response.set_status_code_validation, kwargs.get("response_status_code_validation"))
        apply_if_kwarg_exists(response.set_body_type_validation, kwargs.get("response_type_validation"))
        apply_if_kwarg_exists(response.set_body_schematic_validation, kwargs.get("response_schematic_validation"))
        apply_if_kwarg_exists(connection.set_timeout, kwargs.get("timeout"))
        apply_if_kwarg_exists(connection.set_ssl_verify, kwargs.get("ssl_verify"))
        connection.set_retry_policy(**kwargs.get("retry_policy", dict()))

        return connection.send(session, request, response)

    def get(self, **kwargs):
        return self._builder(HTTPMethod.GET, **kwargs)

    def post(self, **kwargs):
        return self._builder(HTTPMethod.POST, **kwargs)

    def put(self, **kwargs):
        return self._builder(HTTPMethod.PUT, **kwargs)

    def delete(self, **kwargs):
        return self._builder(HTTPMethod.DELETE, **kwargs)

    def patch(self, **kwargs):
        return self._builder(HTTPMethod.PATCH, **kwargs)
