# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pytest


@pytest.fixture(scope='session')
def sts_environment():
    yield


@pytest.fixture
def instance():
    return {
        'aws_access_key_id': 'abc',
        'aws_secret_access_key': 'cde',
        'role_arn': 'arn:aws:iam::0123456789:role/OtherRoleName',
        'region': 'ijk'
    }


@pytest.fixture
def instance_no_role_arn():
    return {
        'aws_access_key_id': 'abc',
        'aws_secret_access_key': 'cde',
        'region': 'ijk'
    }
