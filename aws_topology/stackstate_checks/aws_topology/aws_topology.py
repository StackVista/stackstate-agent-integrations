# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import boto3
from schematics import Model
from schematics.types import StringType, ListType, DictType
from botocore.config import Config
from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.checks.aws import AWSTopologyBaseCheck


DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

DEFAULT_COLLECTION_INTERVAL = 60


class State(Model):
    code = StringType(required=True)


class InstanceInfo(Model):
    region = StringType(required=True)
    aws_access_key_id = StringType(required=True)
    aws_secret_access_key = StringType(required=True)
    role_arn = StringType(required=True)
    account_id = StringType(required=True)
    tags = ListType(StringType, default=[])
    arns = DictType(StringType, default={})
    apis_to_run = ListType(StringType)


class AwsTopologyCheck(AWSTopologyBaseCheck):
    """Collects AWS Topology and sends them to STS."""
    INSTANCE_TYPE = 'aws'  # TODO should we add _topology?
    SERVICE_CHECK_CONNECT_NAME = 'aws_topology.can_connect'
    SERVICE_CHECK_EXECUTE_NAME = 'aws_topology.can_execute'
    INSTANCE_SCHEMA = InstanceInfo

    def get_instance_key(self, instance_info):
        return TopologyInstance(self.INSTANCE_TYPE, str(instance_info.account_id))

    def check(self, instance_info):
        try:
            aws_client = AwsClient(instance_info, self.init_config)
            instance_info.region = aws_client.region
            account_id = aws_client.get_account_id()
            if not account_id == instance_info.account_id:
                raise Exception(
                    "AWS caller identity does not return correct account_id. %s was returned, but %s was expected." %
                    (account_id, instance_info.account_id)
                )
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.OK, tags=instance_info.tags)
        except Exception as e:
            msg = 'AWS connection failed: {}'.format(e)
            self.log.error(msg)
            self.service_check(
                self.SERVICE_CHECK_CONNECT_NAME,
                AgentCheck.CRITICAL,
                message=msg,
                tags=instance_info.tags
            )
            return

        try:
            self.get_topology(instance_info, aws_client)
            self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.OK, tags=instance_info.tags)
        except Exception as e:
            msg = 'AWS topology collection failed: {}'.format(e)
            self.log.error(msg)
            self.service_check(
                self.SERVICE_CHECK_EXECUTE_NAME,
                AgentCheck.CRITICAL,
                message=msg,
                tags=instance_info.tags
            )


class AwsClient:
    def __init__(self, instance, config):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)

        aws_access_key_id = instance.aws_access_key_id
        aws_secret_access_key = instance.aws_secret_access_key
        role_arn = instance.role_arn
        self.region = instance.region
        self.aws_session_token = None

        if aws_secret_access_key and aws_access_key_id and role_arn and self.region:
            sts_client = boto3.client(
                'sts',
                config=DEFAULT_BOTO3_CONFIG,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='sts-agent-check')
            self.aws_access_key_id = role['Credentials']['AccessKeyId']
            self.aws_secret_access_key = role['Credentials']['SecretAccessKey']
            self.aws_session_token = role['Credentials']['SessionToken']
        if self.aws_session_token is None:
            raise Exception("Received no session token during AWS client initialization")

    def get_account_id(self):
        return self.get_boto3_client('sts').get_caller_identity().get('Account')

    def get_boto3_client(self, service_name, region=None):
        return boto3.client(service_name, region_name=region or self.region, config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=self.aws_session_token)
