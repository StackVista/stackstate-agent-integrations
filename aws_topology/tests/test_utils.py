from stackstate_checks.aws_topology.resources.utils import (
    make_valid_data,
    get_partition_name,
    extract_dimension_name,
    replace_stage_variables,
    custom_list_data_comparator,
    client_array_operation,
    transformation,
    set_required_access_v2,
    create_security_group_relations,
    get_ipurns_from_hostname,
)
from stackstate_checks.aws_topology.utils import correct_tags
from datetime import datetime
import unittest
from six import string_types
import sys
import botocore
from mock import patch


class TestUtils(unittest.TestCase):
    def test_utils_make_valid_data_converts_date_to_str(self):
        x = datetime.now()
        self.assertIsInstance(make_valid_data(x), string_types)

    def test_utils_make_valid_data_converts_instance_to_str(self):
        self.assertIsInstance(make_valid_data(self), string_types)

    def test_utils_partition_name(self):
        self.assertEqual(get_partition_name("eu-west-1"), "aws")
        self.assertEqual(get_partition_name("us-gov-east-1"), "aws-us-gov")
        self.assertEqual(get_partition_name("us-gov-west-1"), "aws-us-gov")
        self.assertEqual(get_partition_name("cn-north-1"), "aws-cn")
        self.assertEqual(get_partition_name("cn-northwest-1"), "aws-cn")
        self.assertEqual(get_partition_name("us-iso-east-1"), "aws-iso")
        self.assertEqual(get_partition_name("us-isob-east-1"), "aws-iso-b")

    def test_utils_extract_dimension_name_no_match_returns_empty_string(self):
        self.assertEqual(extract_dimension_name("test", "fake"), "")

    def test_utils_replace_stage_variables(self):
        self.assertEqual(replace_stage_variables("test", {}), "test")
        self.assertEqual(replace_stage_variables("${stageVariables.test}", {"test": "test"}), "test")

    def test_utils_custom_list_data_comparator(self):
        if sys.version_info.major == 3:
            self.assertEqual(custom_list_data_comparator(self, 1), -1)
        else:
            self.assertEqual(custom_list_data_comparator(self, 1), 1)

    def test_utils_client_array_operation(self):
        with self.assertRaises(Exception):
            for x in client_array_operation(self, "nottobefound", "Any"):
                pass

        class TestClient(object):
            def can_paginate(self, operation_name):
                return False

            def get_array(self):
                return {"arr": [1, 2, 3]}

        c = TestClient()
        for x in client_array_operation(c, "get_array", "arr"):
            pass

    def test_utils_transformation(self):
        warnings = []

        class Agent(object):
            def warning(self, txt):
                warnings.append("test")

        class MyTest(object):
            def __init__(self):
                self.agent = Agent()

            @transformation()
            def testtrans(self):
                raise Exception("stop")

        x = MyTest()
        with self.assertRaises(Exception):
            x.testtrans()

        self.assertEqual(warnings, ["test"])

    def test_utils_set_not_authorized(self):
        class Agent(object):
            def __init__(self):
                self.role_name = "testrole"

            def warning(self, txt):
                warnings.append(txt)

        class Collector(object):
            def __init__(self):
                self.agent = Agent()

            @set_required_access_v2("test")
            def test(self):
                raise botocore.exceptions.ClientError({"Error": {"Code": "AccessDenied"}}, "get_access_denied")

            @set_required_access_v2("test")
            def test_throttle(self):
                raise botocore.exceptions.ClientError({"Error": {"Code": "Throttling"}}, "get_throttled")

            @set_required_access_v2("test", ignore_codes=["NoSuchTagSet"])
            def test_ignore_codes(self):
                raise botocore.exceptions.ClientError({"Error": {"Code": "NoSuchTagSet"}}, "get_ignore_code")

            @set_required_access_v2("test")
            def test_other(self):
                raise botocore.exceptions.ClientError({"Error": {"Code": "RandomErrorCode"}}, "get_other")

        warnings = []
        c = Collector()
        c.test()
        self.assertEqual(warnings, ["Role testrole needs test"])

        warnings = []
        c = Collector()
        c.test_throttle()
        self.assertEqual(warnings, ["throttling"])

        warnings = []
        c = Collector()
        c.test_ignore_codes()
        self.assertEqual(warnings, ["Error code NoSuchTagSet returned but is explicitly ignored"])

        warnings = []
        with self.assertRaises(Exception):
            c = Collector()
            c.test_other()
        self.assertEqual(warnings, [])

    def test_utils_create_security_group_relations(self):
        data = {}
        self.assertIsNone(create_security_group_relations("id", data, None))

    def test_utils_correct_tags(self):
        tags = [{"key": "test", "value": "test"}]
        data = {"tags": tags}
        self.assertEqual(correct_tags(data), {"tags": tags, "Tags": {"test": "test"}})
        data = {"Tags": [{"Key": "test", "Value": "test"}]}
        self.assertEqual(correct_tags(data), {"Tags": {"test": "test"}})

    def test_utils_get_ipurns_from_hostname(self):
        with patch('socket.getaddrinfo', return_value=((0, 0, 0, 0, ['10.1.1.10']),)):
            self.assertEqual(get_ipurns_from_hostname('test1', 'vpc-123'), ['urn:vpcip:vpc-123/10.1.1.10'])
        with patch('socket.getaddrinfo', return_value=((0, 0, 0, 0, ['197.128.230.1']),)):
            self.assertEqual(get_ipurns_from_hostname('test1', 'vpc-123'), ['urn:host:/197.128.230.1'])
