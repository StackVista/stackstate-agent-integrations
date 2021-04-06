# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    #  This conf instance is used when running `checksdev env start mycheck myenv`.
    #  The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    #  If you want to run an environment this object can not be empty.
    return {
        "aws_access_key_id": "some_key",
        "aws_secret_access_key": "some_secret",
        "role_arn": "some_role",
        "account_id": "123456789012",
        "region": "eu-west-1"
    }


@pytest.fixture(scope="class")
def instance(request):
    cfg = {
        "aws_access_key_id": "some_key",
        "aws_secret_access_key": "some_secret",
        "role_arn": "some_role",
        "account_id": "123456789012",
        "region": "eu-west-1"
    }
    request.cls.instance = cfg
