from six import string_types, integer_types
import re
import hashlib
import json
from datetime import datetime, date
from schematics import Model
from botocore.exceptions import ClientError


def make_valid_data_internal(data):
    if isinstance(data, list):
        return [make_valid_data_internal(x) for x in data]
    elif isinstance(data, dict):
        return {key: make_valid_data_internal(val) for key, val in data.items()}
    elif data is None or isinstance(data, string_types) or isinstance(data, integer_types) or \
            isinstance(data, float) or isinstance(data, bool):
        return data
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    else:
        return str(data)


def make_valid_data(data):
    result = make_valid_data_internal(data)
    if 'ResponseMetadata' in result:
        result.pop('ResponseMetadata')
    return result


def get_partition_name(region):
    region_string = region.lower()
    partition = 'aws'
    if region_string.startswith("cn-"):
        partition = "aws-cn"
    elif region_string.startswith("us-iso-"):
        partition = "aws-iso"
    elif region_string.startswith("us-isob"):
        partition = "aws-iso-b"
    elif region_string.startswith("us-gov"):
        partition = "aws-us-gov"
    return partition


def create_arn(resource='', region='', account_id='', resource_id=''):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}".format(resource, region, account_id, resource_id)


def create_resource_arn(resource, region, account_id, sub_resource, resource_id):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}/{}".format(resource, region, account_id, sub_resource, resource_id)


def create_host_urn(instance_id):
    return "urn:host:/{}".format(instance_id)


def with_dimensions(dimensions):
    return {'CW': {'Dimensions': dimensions}}


def extract_dimension_name(arn, resource_type):
    regex = r"arn:aws:[a-zA-Z0-9]*:[a-zA-Z0-9\-]*:[a-zA-Z0-9]*:{}\/(.*)".format(resource_type)
    try:
        match = re.search(regex, arn)
        return match.group(1)
    except Exception as err:
        print(str(err))
        return ""


def update_dimensions(data, dimensions):
    return data['CW'].get('Dimensions').append(dimensions)


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
    if len(variables) == 0:
        return string

    replacements = {'${stageVariables.' + name + '}': value for (name, value) in variables.items()}
    # Place longer ones first to keep shorter substrings from matching where the longer ones should take place
    # For instance given the replacements {'ab': 'AB', 'abc': 'ABC'} against the string 'hey abc', it should produce
    # 'hey ABC' and not 'hey ABc'
    substrs = sorted(replacements, key=len, reverse=True)

    # Create a big OR regex that matches any of the substrings to replace
    regexp = re.compile('|'.join(map(re.escape, substrs)))

    # For each match, look up the new string in the replacements
    return regexp.sub(lambda match: replacements[match.group(0)], string)


def create_security_group_relations(resource_id, resource_data, agent, security_group_field='SecurityGroups'):
    if resource_data.get(security_group_field):
        for security_group_id in resource_data[security_group_field]:
            agent.relation(resource_id, security_group_id, 'uses service', {})


def create_hash(dict):
    return hashlib.sha256(str(json.dumps(dict, sort_keys=True)).encode('utf-8')).hexdigest()


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


class CloudTrailEventBase(Model):
    def _internal_process(self, event_name, session, location, agent):
        raise NotImplementedError

    def process(self, event_name, session, location, agent):
        self._internal_process(event_name, session, location, agent)


def set_required_access(value):
    def inner(func):
        cls = func.__class__
        access = getattr(cls, 'iam_access', [])
        access.append(value)
        return func

    return inner


_THROTTLED_ERROR_CODES = [
    'Throttling',
    'ThrottlingException',
    'ThrottledException',
    'RequestThrottledException',
    'TooManyRequestsException',
    'ProvisionedThroughputExceededException',
    'TransactionInProgressException',
    'RequestLimitExceeded',
    'BandwidthLimitExceeded',
    'LimitExceededException',
    'RequestThrottled',
    'SlowDown',
    'PriorRequestNotComplete',
    'EC2ThrottledException',
]


def is_throttling_error(code):
    return code in _THROTTLED_ERROR_CODES


def set_required_access_v2(value):
    def decorator(func):
        def inner_function(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                return result
            except ClientError as e:
                error = e.response.get('Error', {})
                code = error.get('Code', 'Unknown')
                if code == 'AccessDenied':
                    self.agent.warning(
                        '{} encountered AccessDenied role {} needs {}'.format(func.__name__, self.agent.role_name,
                                                                              value),
                        **kwargs
                    )
                elif is_throttling_error(code):
                    self.agent.warning(
                        'throttling'
                    )
                else:
                    raise e

        return inner_function

    return decorator
