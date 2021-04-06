# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import traceback
import boto3
from schematics import Model
from schematics.types import StringType, ListType, DictType
from botocore.config import Config
from copy import deepcopy
from stackstate_checks.base import AgentCheck, TopologyInstance

from .utils import location_info

from .resources import (
    process_s3,
    process_vpn_gateways,
    process_vpcs,
    process_auto_scaling,
    process_api_gateway,
    process_security_group,
    process_elb_v2,
    process_sns,
    process_firehose
)

memory_data = {}  # name -> arn for cloudformation

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

DEFAULT_COLLECTION_INTERVAL = 60

ALL_APIS = {
    's3': {
        'parts': [
            process_s3
        ]
    },
    'ec2': {
        'parts': [
            process_vpn_gateways,
            process_vpcs,
            process_security_group
        ]
    },
    'elbv2': {
        'parts': [
            process_elb_v2
        ],
        'memory_key': 'target_group'
    },
    'autoscaling': {
        'parts': [
            process_auto_scaling
        ]
    },
    'apigateway': {
        'parts': [
            process_api_gateway
        ],
        'memory_key': 'api_stage'
    },
    'sns': {
        'parts': [
            process_sns
        ]
    },
    'firehose': {
        'parts': [
            process_firehose
        ]
    }
}


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


class AwsTopologyCheck(AgentCheck):
    """Collects AWS Topology and sends them to STS."""
    INSTANCE_TYPE = 'aws'  # TODO should we add _topology?
    SERVICE_CHECK_CONNECT_NAME = 'aws_topology.can_connect'
    SERVICE_CHECK_EXECUTE_NAME = 'aws_topology.can_execute'
    INSTANCE_SCHEMA = InstanceInfo
    APIS = deepcopy(ALL_APIS)

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
            self._get_topology(instance_info, aws_client)
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

    def _get_topology(self, instance_info, aws_client):
        """Gets AWS Topology returns them in Agent format."""
        self.start_snapshot()

        # TODO https://docs.aws.amazon.com/AWSEC2/latest/APIReference/throttling.html
        keys = self.APIS.keys()
        if instance_info.apis_to_run is not None:
            keys = instance_info.apis_to_run
        location = location_info(instance_info.account_id, instance_info.region)
        errors = []
        for api in keys:
            try:
                client = aws_client._get_boto3_client(api)
                for part in self.APIS[api]['parts']:
                    result = part(location, client, self)
                    if result:
                        memory_key = self.APIS[api].get('memory_key') or api
                        if memory_data.get(memory_key) is not None:
                            memory_data[memory_key].update(result)
                        else:
                            memory_data[memory_key] = result
            except Exception:
                errors.append('API %s ended with exception: %s' % (api, traceback.format_exc()))
        if len(errors) > 0:
            raise Exception('get_topology gave following exceptions: %s' % ', '.join(errors))

        self.stop_snapshot()


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
            sts_client = boto3.client('sts', config=DEFAULT_BOTO3_CONFIG, aws_access_key_id=aws_access_key_id,
                                      aws_secret_access_key=aws_secret_access_key)
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='sts-agent-check')
            self.aws_access_key_id = role['Credentials']['AccessKeyId']
            self.aws_secret_access_key = role['Credentials']['SecretAccessKey']
            self.aws_session_token = role['Credentials']['SessionToken']
        if self.aws_session_token is None:
            raise Exception("Received no session token during AWS client initialization")

    def get_account_id(self):
        return self._get_boto3_client('sts').get_caller_identity().get('Account')

    def _get_boto3_client(self, service_name):
        return boto3.client(service_name, region_name=self.region, config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=self.aws_session_token)
