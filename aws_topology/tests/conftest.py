# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


REGION = "test-region"
KEY_ID = "1234"
ACCESS_KEY = "5678"
ACCOUNT_ID = "123456789012"
WRONG_ACCOUNT_ID = "987654321012"
ROLE = "some_role_with_many_characters"
TOKEN = "ABCDE"

API_RESULTS = {
    'AssumeRole': {
        "Credentials": {
            "AccessKeyId": KEY_ID,
            "SecretAccessKey": ACCESS_KEY,
            "SessionToken": TOKEN
        }
    },
    'GetCallerIdentity': {
        "Account": ACCOUNT_ID,
    },
}


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "role_arn": "arn:aws:iam::123456789012:role/RoleName",
        "regions": ["eu-west-1"],
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
            "role_arn": "arn:aws:iam::123456789012:role/RoleName",
            "regions": ["eu-west-1"],
    }
    request.cls.instance = cfg


@pytest.fixture(scope="class")
def init_config(request):
    cfg = {
        "aws_access_key_id": "abc",
        "aws_secret_access_key": "cde",
        "external_id": "randomvalue"
    }
    request.cls.config = cfg


@pytest.fixture(scope="class")
def init_config_override(request):
    cfg = {
        "aws_access_key_id": "abc",
        "aws_secret_access_key": "cde",
        "external_id": "disable_external_id_this_is_unsafe",
    }
    request.cls.config = cfg
