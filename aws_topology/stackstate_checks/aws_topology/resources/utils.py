from six import ensure_text, string_types, integer_types
import re
import hashlib
import sys
import json
from datetime import datetime, date
from botocore.exceptions import ClientError
from functools import cmp_to_key
import socket

try:
    import ipaddress
except ImportError:
    try:
        from pip._vendor import ipaddress  # type: ignore
    except ImportError:
        import ipaddr as ipaddress  # type: ignore

        ipaddress.ip_address = ipaddress.IPAddress  # type: ignore
        ipaddress.ip_network = ipaddress.IPNetwork  # type: ignore


def make_valid_data_internal(data):
    if isinstance(data, list):
        return [make_valid_data_internal(x) for x in data]
    elif isinstance(data, dict):
        return {key: make_valid_data_internal(val) for key, val in data.items()}
    elif (
        data is None
        or isinstance(data, string_types)
        or isinstance(data, integer_types)
        or isinstance(data, float)
        or isinstance(data, bool)
    ):
        return data
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    else:
        return str(data)


def make_valid_data(data):
    result = make_valid_data_internal(data)
    if "ResponseMetadata" in result:
        result.pop("ResponseMetadata")
    return result


def get_partition_name(region):
    region_string = region.lower()
    partition = "aws"
    if region_string.startswith("cn-"):
        partition = "aws-cn"
    elif region_string.startswith("us-iso-"):
        partition = "aws-iso"
    elif region_string.startswith("us-isob"):
        partition = "aws-iso-b"
    elif region_string.startswith("us-gov"):
        partition = "aws-us-gov"
    return partition


def create_arn(resource="", region="", account_id="", resource_id=""):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}".format(resource, region, account_id, resource_id)


def create_resource_arn(resource, region, account_id, sub_resource, resource_id):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}/{}".format(resource, region, account_id, sub_resource, resource_id)


def create_host_urn(instance_id):
    return "urn:host:/{}".format(instance_id)


def with_dimensions(dimensions):
    return {"CW": {"Dimensions": dimensions}}


def extract_dimension_name(arn, resource_type):
    regex = r"arn:aws:[a-zA-Z0-9]*:[a-zA-Z0-9\-]*:[a-zA-Z0-9]*:{}\/(.*)".format(resource_type)
    try:
        match = re.search(regex, arn)
        return match.group(1)
    except Exception as err:
        print(str(err))
        return ""


def update_dimensions(data, dimensions):
    return data["CW"].get("Dimensions").append(dimensions)


# Based on StackOverflow: https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
# And Gist: https://gist.github.com/bgusach/a967e0587d6e01e889fd1d776c5f3729
def replace_stage_variables(string, variables):
    """
    Given a string and a replacement map, it returns the replaced string.
    :param str string: string to execute replacements on
    :param dict variables: replacement dictionary {value to find: value to replace}
    :rtype: str
    """
    # Make sure there's something that needs to be replaced
    if not variables:
        return string

    replacements = {"${stageVariables." + name + "}": value for (name, value) in variables.items()}
    # Place longer ones first to keep shorter substrings from matching where the longer ones should take place
    # For instance given the replacements {'ab': 'AB', 'abc': 'ABC'} against the string 'hey abc', it should produce
    # 'hey ABC' and not 'hey ABc'
    substrs = sorted(replacements, key=len, reverse=True)

    # Create a big OR regex that matches any of the substrings to replace
    regexp = re.compile("|".join(map(re.escape, substrs)))

    # For each match, look up the new string in the replacements
    return regexp.sub(lambda match: replacements[match.group(0)], string)


def create_security_group_relations(resource_id, resource_data, agent, security_group_field="SecurityGroups"):
    if resource_data.get(security_group_field):
        for security_group_id in resource_data[security_group_field]:
            agent.relation(resource_id, security_group_id, "uses-service", {})  # TODO


def deep_sort_lists(value):
    """
    Custom sorting implemented as a wrapper on top of Python's built-in ``sorted`` method. This is necessary because
    the previous behavior assumed lists were unordered. As part of migration to Py3, we are trying to
    retain the same behavior. But in Py3, lists with complex data types like dict cannot be sorted. Hence
    we provide a custom sort function that tries best sort the lists in a stable order. The actual order
    does not matter as long as it is stable between runs.
    This implementation assumes that the input was parsed from a JSON data. So it can have one of the
    following types: a primitive type, list or other dictionaries.
    We traverse the dictionary like how we would traverse a tree. If a value is a list, we recursively sort the members
    of the list, and then sort the list itself.
    This assumption that lists are unordered is a problem at the first place. As part of dropping support for Python2,
    we should remove this assumption.
    """

    if isinstance(value, dict):
        return {k: deep_sort_lists(v) for k, v in value.items()}
    if isinstance(value, list):
        if sys.version_info.major < 3:
            # Py2 can sort lists with complex types like dictionaries
            return sorted((deep_sort_lists(x) for x in value))
        else:
            # Py3 cannot sort lists with complex types. Hence a custom comparator function
            return sorted((deep_sort_lists(x) for x in value), key=cmp_to_key(custom_list_data_comparator))
    else:
        return value


def custom_list_data_comparator(obj1, obj2):
    """
    Comparator function used to sort lists with complex data types in them. This is meant to be used only within the
    context of sorting lists for use with unit tests.
    Given any two objects, this function will return the "difference" between the two objects. This difference obviously
    does not make sense for complex data types like dictionaries & list. This function implements a custom logic that
    is partially borrowed from Python2's implementation of such a comparison:
    * Both objects are dict: Convert them JSON strings and compare
    * Both objects are comparable data types (ie. ones that have > and < operators): Compare them directly
    * Objects are non-comparable (ie. one is a dict other is a list): Compare the names of the data types.
      ie. dict < list because of alphabetical order. This is Python2's behavior.
    """

    if isinstance(obj1, dict) and isinstance(obj2, dict):
        obj1 = json.dumps(obj1, sort_keys=True)
        obj2 = json.dumps(obj2, sort_keys=True)

    try:
        return (obj1 > obj2) - (obj1 < obj2)
    # In Py3 a TypeError will be raised if obj1 and obj2 are different types or uncomparable
    except TypeError:
        s1, s2 = type(obj1).__name__, type(obj2).__name__
        return (s1 > s2) - (s1 < s2)


def create_hash(dict):
    return hashlib.sha256(str(json.dumps(deep_sort_lists(dict), sort_keys=True)).encode("utf-8")).hexdigest()


def client_array_operation(client, operation_name, array_field_name, **kwargs):
    method = getattr(client, operation_name, None)
    if method is None:
        raise Exception("Method not found")
    if client.can_paginate(operation_name):
        for page in client.get_paginator(operation_name).paginate(**kwargs):
            for item in page.get(array_field_name) or []:
                yield item
    else:
        for item in method(**kwargs).get(array_field_name) or []:
            yield item


_THROTTLED_ERROR_CODES = [
    "Throttling",
    "ThrottlingException",
    "ThrottledException",
    "RequestThrottledException",
    "TooManyRequestsException",
    "ProvisionedThroughputExceededException",
    "TransactionInProgressException",
    "RequestLimitExceeded",
    "BandwidthLimitExceeded",
    "LimitExceededException",
    "RequestThrottled",
    "SlowDown",
    "PriorRequestNotComplete",
    "EC2ThrottledException",
]


def is_throttling_error(code):
    return code in _THROTTLED_ERROR_CODES


def set_required_access_v2(value, ignore_codes=[]):
    def decorator(func):
        def inner_function(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                return result
            except ClientError as e:
                error = e.response.get("Error", {})
                code = error.get("Code", "Unknown")
                if code in ["AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "AuthorizationError"]:
                    iam_access = value if not isinstance(value, list) else ", ".join(value)
                    self.agent.warning("Role {} needs {}".format(self.agent.role_name, iam_access), **kwargs)
                elif is_throttling_error(code):
                    self.agent.warning("throttling")
                elif code in ignore_codes:
                    self.agent.warning("Error code {} returned but is explicitly ignored".format(code))
                else:
                    raise e

        return inner_function

    return decorator


def transformation():
    def decorator(func):
        def inner_function(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                return result
            except Exception as e:
                self.agent.warning("Transformation failed in {}".format(func.__name__), **kwargs)
                raise e  # to stop further processing

        return inner_function

    return decorator


def is_private(ip):
    return ipaddress.ip_address(ensure_text(ip)).is_private


def ipaddress_to_urn(ip, vpc_id):
    if is_private(ip):
        return "urn:vpcip:{}/{}".format(vpc_id, ip)
    else:
        return create_host_urn(ip)


def get_ipurns_from_hostname(host_name, vpc_id):
    result = []
    ai = socket.getaddrinfo(host_name, 0, socket.AF_INET)
    ips = set(i[4][0] for i in ai)
    for ip in ips:
        result.append(ipaddress_to_urn(ip, vpc_id))
    return result
