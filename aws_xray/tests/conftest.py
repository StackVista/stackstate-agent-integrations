# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time

import pytest
import boto3
import os


HERE = os.path.dirname(os.path.abspath(__file__))
STACKNAME = "xray-test"


def boto(resource):
    return boto3.client(resource)


def create_stack():

    def _parse_template():
        with open(os.path.join(HERE, 'cloudformation_template', 'xray_template.yaml')) as template_fileobj:
            template_data = template_fileobj.read()
        return template_data
    boto('cloudformation').create_stack(StackName=STACKNAME, TemplateBody=_parse_template(),
                                        Capabilities=['CAPABILITY_NAMED_IAM'],
                                        Tags=[{'Key': 'xray-integration', 'Value': 'True'}])
    waiter = boto('cloudformation').get_waiter('stack_create_complete')
    print("...waiting for stack to be ready...")
    waiter.wait(StackName=STACKNAME)


def delete_stack():
    boto('cloudformation').delete_stack(StackName=STACKNAME)
    waiter = boto('cloudformation').get_waiter('stack_delete_complete')
    print("...waiting for stack to be deleted...")
    waiter.wait(StackName=STACKNAME)


@pytest.fixture(scope='session')
def sts_environment():
    yield


@pytest.fixture
def xray_instance():
    # invoke the lambda function to create some traces in background
    boto('lambda').invoke(FunctionName="TestCreateTrace")
    # Wait for the traces to be generated for processing
    time.sleep(20)
    return {
        'aws_access_key_id': os.environ.get("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.environ.get("AWS_SECRET_ACCESS_KEY"),
        'region': os.environ.get("AWS_DEFAULT_REGION")
    }


@pytest.fixture(scope='session')
def xray_integration(request):
    create_stack()

    def tear_down():
        delete_stack()
    request.addFinalizer(tear_down)

    yield True


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
