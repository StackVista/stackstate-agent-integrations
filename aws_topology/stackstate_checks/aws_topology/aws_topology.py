# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import boto3
import time
import traceback
from botocore.exceptions import ClientError
from schematics import Model
from schematics.types import StringType, ListType, DictType
from botocore.config import Config
from stackstate_checks.base import AgentCheck, TopologyInstance
from .resources import ResourceRegistry
from .utils import location_info

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

DEFAULT_COLLECTION_INTERVAL = 60


class InitConfig(Model):
    aws_access_key_id = StringType(required=True)
    aws_secret_access_key = StringType(required=True)
    external_id = StringType(required=True)


class InstanceInfo(Model):
    role_arn = StringType(required=True)
    regions = ListType(StringType)
    tags = ListType(StringType, default=[])
    arns = DictType(StringType, default={})
    apis_to_run = ListType(StringType)


class AwsTopologyCheck(AgentCheck):
    """Collects AWS Topology and sends them to STS."""
    INSTANCE_TYPE = 'aws'  # TODO should we add _topology?
    SERVICE_CHECK_CONNECT_NAME = 'aws_topology.can_connect'
    SERVICE_CHECK_EXECUTE_NAME = 'aws_topology.can_execute'
    INSTANCE_SCHEMA = InstanceInfo

    def get_account_id(self, instance_info):
        return instance_info.role_arn.split(':')[4]

    def get_instance_key(self, instance_info):
        return TopologyInstance(self.INSTANCE_TYPE, str(self.get_account_id(instance_info)))

    def check(self, instance_info):
        try:
            aws_client = AwsClient(self.init_config)
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

    def get_topology(self, instance_info, aws_client):
        """Gets AWS Topology returns them in Agent format."""
        self.start_snapshot()

        self.memory_data = {}  # name -> arn for cloudformation
        errors = []
        self.delete_ids = []

        for region in instance_info.regions:
            session = aws_client.get_session(instance_info.role_arn, region)
            registry = ResourceRegistry.get_registry()["regional" if region != "global" else "global"]
            keys = (
                [key for key in registry.keys()]
                if instance_info.apis_to_run is None
                else [api.split('|')[0] for api in instance_info.apis_to_run]
            )
            # move cloudformation to the end
            if 'cloudformation' in keys:
                keys.append(keys.pop(keys.index('cloudformation')))
            for api in keys:
                client = session.client(api)
                location = location_info(self.get_account_id(instance_info), session.region)
                for part in registry[api]:
                    if instance_info.apis_to_run is not None:
                        if not (api + '|' + part) in instance_info.apis_to_run:
                            continue
                    processor = registry[api][part](location, client, self)
                    try:
                        if api != 'cloudformation':
                            result = processor.process_all()
                        else:
                            result = processor.process_all(self.memory_data)
                        if result:
                            memory_key = processor.MEMORY_KEY or api
                            if memory_key != "MULTIPLE":
                                if self.memory_data.get(memory_key) is not None:
                                    self.memory_data[memory_key].update(result)
                                else:
                                    self.memory_data[memory_key] = result
                            else:
                                for rk in result:
                                    if self.memory_data.get(rk) is not None:
                                        self.memory_data[rk].update(result[rk])
                                    else:
                                        self.memory_data[rk] = result[rk]
                        self.delete_ids += processor.get_delete_ids()
                    except Exception as e:
                        event = {
                            'timestamp': int(time.time()),
                            'event_type': 'aws_agent_check_error',
                            'msg_title': e.__class__.__name__ + " in api " + api + " component_type " + part,
                            'msg_text': str(e),
                            'tags': [
                                'aws_region:' + location["Location"]["AwsRegion"],
                                'account_id:' + location["Location"]["AwsAccount"],
                                'process:' + api + "|" + part
                            ]
                        }
                        self.event(event)
                        errors.append('API %s ended with exception: %s %s' % (api, str(e), traceback.format_exc()))
        if len(errors) > 0:
            raise Exception('get_topology gave following exceptions: %s' % ', '.join(errors))

        self.stop_snapshot()


class AwsClient:
    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)
        self.external_id = config.external_id
        self.aws_access_key_id = config.aws_access_key_id
        self.aws_secret_access_key = config.aws_secret_access_key

        if self.aws_secret_access_key and self.aws_access_key_id:
            self.sts_client = boto3.client(
                'sts',
                config=DEFAULT_BOTO3_CONFIG,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
        else:
            # Rely on credential provider chain to find credentials
            try:
                self.sts_client = boto3.client(
                    'sts',
                    config=DEFAULT_BOTO3_CONFIG
                )
            except Exception as e:
                raise Exception('No credentials found, the following exception was given: %s' % e)

    def get_session(self, role_arn, region):
        try:
            # This should fail as it means it was able to successfully use the role without an external ID
            role = self.sts_client.assume_role(RoleArn=role_arn, RoleSessionName='sts-agent-id-test')
            # This override should not be (publicly) documented
            if self.external_id != 'disable_external_id_this_is_unsafe':
                raise Exception(
                    'No external ID has been set for this role.' +
                    'For security reasons, please set the external ID.'
                )
        except ClientError as error:
            if error.response['Error']['Code'] == 'AccessDeniedException':
                try:
                    role = self.sts_client.assume_role(
                        RoleArn=role_arn,
                        RoleSessionName='sts-agent-check-%s' % region,
                        ExternalId=self.external_id
                        )
                except Exception as error:
                    raise Exception('Unable to assume role %s. Error: %s' % (role_arn, error))
            else:
                raise error

        return boto3.Session(
            region_name=region if region != 'global' else 'us-east-1',
            aws_access_key_id=role['Credentials']['AccessKeyId'],
            aws_secret_access_key=role['Credentials']['SecretAccessKey'],
            aws_session_token=role['Credentials']['SessionToken']
        )
