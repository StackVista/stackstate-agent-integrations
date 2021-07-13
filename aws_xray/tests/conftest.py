# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import shutil
import pytest
from stackstate_checks.aws_xray import AwsCheck


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


@pytest.fixture
def aws_check(instance):
    # setUp the check
    instance['role_arn'] = '672574731473'
    aws_check = AwsCheck('aws', {}, {}, [instance])
    yield aws_check
    # tearDown by clearing the files and state
    state_descriptor = aws_check._get_state_descriptor()
    aws_check.state_manager.clear(state_descriptor)
    shutil.rmtree(aws_check.get_check_state_path(), ignore_errors=True)
