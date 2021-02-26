from enum import Enum
from schematics.models import Model
from schematics.types import StringType, URLType, DictType,  BooleanType, IntType
from schematics.exceptions import ValidationError


"""
"""


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


"""
"""


class _HTTPBasicAuth(Model):
    username = StringType(required=True)
    password = StringType(required=True)


class HTTPAuthenticationType(Enum):
    NoAuth = None
    BasicAuth = _HTTPBasicAuth


"""
"""


class HTTPRequestType(Enum):
    JSON = dict


"""
"""


class HTTPResponseTypes(Enum):
    TEXT = 'TEXT'
    JSON = 'JSON'
    XML = 'XML'






"""
Extra
"""
class TypiCodeCreateResource(Model):
    title = StringType(required=True)
    body = StringType(required=True)
    userId = IntType(required=True)
