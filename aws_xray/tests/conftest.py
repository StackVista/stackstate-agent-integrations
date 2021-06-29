# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import time

import pytest
import boto3
import os


# HERE = os.path.dirname(os.path.abspath(__file__))
# LAMBDA_PACKAGE_FILE = 'xray-trace.zip'
# LAMBDA_PACKAGE_PATH = os.path.join(HERE, 'cloudformation/xray-package', LAMBDA_PACKAGE_FILE)
# STACK_NAME = "xray-test"
# BUCKET_NAME = "xray-trace-test"


def boto(resource):
    return boto3.client(resource, region_name=os.environ.get("AWS_REGION"))


# def create_stack():
#
#     def _parse_template():
#         with open(os.path.join(HERE, 'cloudformation', 'xray_template.yaml')) as template_fileobj:
#             template_data = template_fileobj.read()
#         return template_data
#     boto('s3').create_bucket(Bucket=BUCKET_NAME, CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
#     # upload the package to s3
#     boto('s3').upload_file(LAMBDA_PACKAGE_PATH, BUCKET_NAME, LAMBDA_PACKAGE_FILE)
#     boto('cloudformation').create_stack(StackName=STACK_NAME, TemplateBody=_parse_template(),
#                                         Capabilities=['CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND'],
#                                         Tags=[{'Key': 'xray-integration', 'Value': 'True'}])
#     waiter = boto('cloudformation').get_waiter('stack_create_complete')
#     print("...waiting for stack to be ready...")
#     waiter.wait(StackName=STACK_NAME)


# def delete_stack():
#     boto('s3').delete_object(Bucket=BUCKET_NAME, Key=LAMBDA_PACKAGE_FILE)
#     boto('s3').delete_bucket(Bucket=BUCKET_NAME)
#     time.sleep(10)
#     boto('cloudformation').delete_stack(StackName=STACK_NAME)
#     waiter = boto('cloudformation').get_waiter('stack_delete_complete')
#     print("...waiting for stack to be deleted...")
#     waiter.wait(StackName=STACK_NAME)


@pytest.fixture(scope='session')
def sts_environment():
    yield


@pytest.fixture
def xray_instance():
    # invoke the lambda function to create some traces in background
    print("Calling the lambda function")
    boto('lambda').invoke(FunctionName="TestCreateTrace")
    # Wait for the traces to be generated for processing
    time.sleep(20)
    return {
        'aws_access_key_id': os.environ.get("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.environ.get("AWS_SECRET_ACCESS_KEY"),
        'region': os.environ.get("AWS_REGION")
    }


@pytest.fixture
def xray_error_instance():
    # invoke the lambda function to create some traces in background
    print("Calling the lambda function")
    payload = b'{"error": {"code": 400, "message": "Some error occurred"}}'
    boto('lambda').invoke(FunctionName="TestCreateTrace", InvocationType="Event", Payload=payload)
    # Wait for the traces to be generated for processing
    time.sleep(20)
    return {
        'aws_access_key_id': os.environ.get("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.environ.get("AWS_SECRET_ACCESS_KEY"),
        'region': os.environ.get("AWS_REGION")
    }


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
