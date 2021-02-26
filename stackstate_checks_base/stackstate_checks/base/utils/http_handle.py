from requests import Session, Request
import json
from http_handle_models import TypiCodeCreateResource, HTTPRequestType, RequestStructure, HTTPMethodEnum, HTTPAuthenticationType, HTTPResponseTypes


class HTTPHelper:
    session = Session()
    request_object = Request()
    error_alternative = None
    request_method_enum_list = [item.value['type'] for item in HTTPMethodEnum]

    def __init__(self):
        self.renew_session()

    def on_error(self, func=None):
        if callable(func) and func is not None:
            self.error_alternative = func

    def on_timeout(self, func=None):
        if callable(func) and func is not None:
            self.error_alternative = func

    def on_auth_failure(self, func=None):
        if callable(func) and func is not None:
            self.error_alternative = func

    def on_failure(self, func=None):
        if callable(func) and func is not None:
            self.error_alternative = func

    def on_success(self, func=None):
        if callable(func) and func is not None:
            self.error_alternative = func

    def handle_error(self, error):
        if self.error_alternative is not None:
            self.error_alternative(error)
        else:
            raise Exception(error)

    def renew_session(self):
        self.session = Session()
        self.request_object = Request()

    def set_http_method(self, http_method):
        available_method_enums = [item.value for item in HTTPMethodEnum]
        available_method_types = [item.value['type'] for item in HTTPMethodEnum]

        # Test if the supplied parameter is a enum
        # If it is then we attempt to find the enum to double check the content and make sure we find it
        if isinstance(http_method, HTTPMethodEnum):
            self.request_object.method = http_method.value['type']

        # Test if the supplied parameter is a normal string
        # We then attempt to find the enum containing that string as the method type
        elif http_method in available_method_types:
            method_type_index = available_method_types.index(http_method)
            if method_type_index > -1 and available_method_enums[method_type_index]:
                self.request_object.method = available_method_enums[method_type_index]['type']

        # If neither then string or enum statements was satisfied then we do not support the requested http method
        else:
            self.request_object.method = None
            error = "HTTP Method `%s` is not supported, Please use any of the following methods %s" % \
                    (http_method, ", ".join(available_method_types))
            self.handle_error(error)

    def set_http_target(self, http_url):
        if isinstance(http_url, str):
            self.request_object.url = http_url
        else:
            self.request_object.url = None
            self.handle_error("Invalid URL specified")

    # C
    def set_http_auth(self, authentication_schematic, authentication_details=None):
        if authentication_schematic.value is None:
            pass
        elif isinstance(authentication_schematic, HTTPAuthenticationType):
            authentication_schematic = authentication_schematic.value(authentication_details)
            authentication_schematic.validate()
        else:
            self.handle_error("Invalid authentication method supplied")

    def set_http_query_parameters(self):
        pass

    def set_http_headers(self, headers=None):
        self.request_object.headers = headers
        pass

    def set_http_proxy_details(self):
        pass

    def set_http_retry_policy(self, max_retries):
        pass

    def set_http_expected_response_type(self, response_type):
        pass


    def set_http_request_body(self, body=None, request_type=None, mapping_model=None):
        if self.request_object.method is None:
            print("Please define the request type before supplying a body")
            return

        # We attempt to find the enum value for the current request object method type
        request_method = HTTPMethodEnum[self.request_object.method] \
            if self.request_object.method in self.request_method_enum_list else None

        # If we found the enum, If the mapped enum do not require a body and no body was supplied
        # Example: A GET request would satisfy the following
        # Success State, We then remove the existing body from the request object
        if request_method is not None and request_method.value.get('body') is False and body is None:
            print("Removed body")
            self.request_object.data = []

        # If we found the enum, If the mapped enum do require a body but no body was supplied
        # Example: A POST request without a body would satisfy the following
        # Failure State, We do require a body to satisfy these type of requests
        elif request_method is not None and request_method.value.get('body') is True and body is None:
            print("Unable to set a empty body for a request that requires a body")
            self.request_object.data = []

        # If the code ends up here then it means that we have a request that contains a body and we supplied a body
        else:
            # If the body supplied is a dict and the mapping model is supplied then we can test the model
            if request_type is not None and type(body) is dict and mapping_model is not None:
                print("Testing to see if the model matches the body request")
                mapping_model(body).validate()
                self.request_object.data = body

            # If the body is a string and we are looking for json
            elif isinstance(body, str) and request_type is HTTPRequestType.JSON:
                print("Attempt to parse the body string to match the JSON type")
                try:
                    parsed_body = json.loads(body)

                    # Test the model if it was supplied
                    if mapping_model is not None:
                        print("Attempt to map the model data to the parse JSON data")
                        mapping_model(parsed_body).validate()
                    self.request_object.data = parsed_body

                except ValueError as e:
                    print("Unable to parse the json data")
                    self.request_object.data = []

            # If the body is a string and we are looking for json
            elif request_type is not None and type(body) is request_type.value:
                print("Correctly defined request type")
                self.request_object.data = body

            # If no types was defined then we attempt o determine if it's JSON
            elif isinstance(body, dict):
                print("JSON Detected")
                self.request_object.data = body

            # At this point we are unable to test the validity of the supplied body as we do not have a test function
            # Thus continue with applying the body to the request
            else:
                print("unable to determine type please specify a type")
                self.request_object.data = []

    # I
    def set_http_ssl_verification(self, verify):
        pass

    # I
    def set_http_timeout(self, timeout):
        pass

    def send_request(self):
        prepared = self.request_object.prepare()

        print('{}\n{}\r\n{}\r\n\r\n{}'.format(
            '---- Request Start ----',
            prepared.method + ' ' + prepared.url,
            '\r\n'.join('{}: {}'.format(k, v) for k, v in prepared.headers.items()),
            prepared.body
        ))
        print('---- Request End ----')

        return self.session.send(prepared)


"""
Flow Example
"""


def error_func(err):
    print("Error:")
    print(err)


def timeout_func(err):
    print("Timeout:")
    print(err)


def auth_failure_func(err):
    print("Timeout:")
    print(err)


def on_failure_func(err):
    print("Timeout:")
    print(err)


def on_success_func(err):
    print("Timeout:")
    print(err)


def post_200_0_headers_body_json():
    request = HTTPHelper()
    request.set_http_method("POST")
    request.set_http_target("https://http-handle.free.beeceptor.com/post/200/0/headers/body/json/v1")
    request.set_http_request_body({
      'title': 'foo',
      'body': 'bar',
      'userId': 1
    }, HTTPRequestType.JSON, TypiCodeCreateResource)
    request.set_http_headers({
        'Content-type': 'application/json'
    })
    response = request.send_request()
    print(response.status_code)
    print(response.content)


post_200_0_headers_body_json()
