from six import string_types, integer_types
import re
import hashlib
import simplejson as json


def make_valid_data(data):
    if isinstance(data, list):
        return [make_valid_data(x) for x in data]
    elif isinstance(data, dict):
        return {key: make_valid_data(val) for key, val in data.items()}
    elif data is None or isinstance(data, string_types) or isinstance(data, integer_types) or \
            isinstance(data, float) or isinstance(data, bool):
        return data
    else:
        return str(data)


def location_info(account_id, region):
    return {'Location': {'AwsAccount': account_id, 'AwsRegion': region}}


def tags_as_dictionary(lisfOfTags, cap_flag=True):
    if lisfOfTags and cap_flag:
        return dict((item['Key'], item['Value']) for item in lisfOfTags)
    elif lisfOfTags and not cap_flag:
        return dict((item['key'], item['value']) for item in lisfOfTags)
    else:
        return {}


def correct_tags(data):
    if 'Tags' in data and isinstance(data['Tags'], list):
        data['Tags'] = tags_as_dictionary(data['Tags'])
    if 'tags' in data and isinstance(data['tags'], list):
        data['Tags'] = tags_as_dictionary(data['tags'], False)
    return data


def create_resource_arn(resource, region, account_id, sub_resource, resource_id):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}/{}".format(resource, region, account_id, sub_resource, resource_id)


def create_arn(resource, region, account_id, resource_id):
    # TODO aws is not always partition!!
    return "arn:aws:{}:{}:{}:{}".format(resource, region, account_id, resource_id)


def with_dimensions(dimensions):
    return {'CW': {'Dimensions': dimensions}}


def extract_dimension_name(arn, resourceType):
    regex = r"arn:aws:[a-zA-Z0-9]*:[a-zA-Z0-9\-]*:[a-zA-Z0-9]*:{}\/(.*)".format(resourceType)
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
    :param dict replacements: replacement dictionary {value to find: value to replace}
    :rtype: str
    """
    # Make sure there's something that needs to be replaced
    if len(variables) == 0:
        return string

    replacements = {'${stageVariables.'+name+'}': value for (name, value) in variables.items()}
    # Place longer ones first to keep shorter substrings from matching where the longer ones should take place
    # For instance given the replacements {'ab': 'AB', 'abc': 'ABC'} against the string 'hey abc', it should produce
    # 'hey ABC' and not 'hey ABc'
    substrs = sorted(replacements, key=len, reverse=True)

    # Create a big OR regex that matches any of the substrings to replace
    regexp = re.compile('|'.join(map(re.escape, substrs)))

    # For each match, look up the new string in the replacements
    return regexp.sub(lambda match: replacements[match.group(0)], string)


def deep_sort(input):

    def do_deep_sort(obj):
        sortby = []

        if isinstance(obj, dict):
            # Note that dicts are order preserving as of Python 3.6
            for k, v in sorted(obj.items()):
                sortby.append(k)
                if isinstance(v, dict) or isinstance(v, list):
                    r = do_deep_sort(v)
                    obj[k] = r[0]
                    sortby = sortby + r[1]
                else:
                    obj[k] = v
                    sortby.append(v)

        if isinstance(obj, list):
            temp = obj
            for i, v in enumerate(obj):
                if isinstance(v, dict) or isinstance(v, list):
                    temp[i] = do_deep_sort(v)
                else:
                    temp[i] = (v, [v])

            temp = sorted(temp, key=lambda v: v[1])
            for i, v in enumerate(temp):
                obj[i] = v[0]
                sortby = sortby + v[1]

        return (obj, sortby)

    return do_deep_sort(input)[0]


def create_hash(dict):
    return hashlib.sha256(str(json.dumps(deep_sort(dict))).encode('utf-8')).hexdigest()


def create_security_group_relations(resource_id, resource_data, agent, security_group_field='SecurityGroups'):
    if resource_data.get(security_group_field):
        for security_group_id in resource_data[security_group_field]:
            agent.relation(resource_id, security_group_id, 'uses service')


def get_partition_name(region):
    region_string = region.lower()
    if region_string.startswith("cn-"):
        partition = "aws-cn"
    elif region_string.startswith("us-iso-"):
        partition = "aws-iso"
    elif region_string.startswith("us-isob"):
        partition = "aws-iso-b"
    elif region_string.startswith("us-gov"):
        partition = "aws-us-gov"
    return partition
