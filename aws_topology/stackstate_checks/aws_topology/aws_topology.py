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
from .resources import ResourceRegistry, type_arn
from .utils import location_info, correct_tags, capitalize_keys
import json
from datetime import datetime
import pytz
import dateutil.parser
import copy


DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT,
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
            init_config = InitConfig(self.init_config)
            init_config.validate()
            aws_client = AwsClient(init_config)
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
            self.delete_ids = []
            self.get_topology(instance_info, aws_client)
            self.get_topology_update(instance_info, aws_client)
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

        errors = []
        agent_proxy = AgentProxy(self, instance_info.role_arn)
        for region in instance_info.regions:
            session = aws_client.get_session(instance_info.role_arn, region)
            registry = ResourceRegistry.get_registry()["regional" if region != "global" else "global"]
            keys = (
                [key for key in registry.keys()]
                if instance_info.apis_to_run is None
                else [api.split('|')[0] for api in instance_info.apis_to_run]
            )
            for api in keys:
                client = None
                location = location_info(self.get_account_id(instance_info), session.region_name)
                agent_proxy.location = copy.deepcopy(location)
                filter = None
                if instance_info.apis_to_run is not None:
                    for to_run in instance_info.apis_to_run:
                        if (api + '|') in to_run:
                            filter = to_run.split('|')[1]
                if client is None:
                    client = session.client(api)
                processor = registry[api](location, client, agent_proxy)
                try:
                    processor.process_all(filter=filter)
                    self.delete_ids += processor.get_delete_ids()
                except Exception as e:
                    event = {
                        'timestamp': int(time.time()),
                        'event_type': 'aws_agent_check_error',
                        'msg_title': e.__class__.__name__ + " in api " + api,
                        'msg_text': str(e),
                        'tags': [
                            'aws_region:' + location["Location"]["AwsRegion"],
                            'account_id:' + location["Location"]["AwsAccount"],
                            'process:' + api
                        ]
                    }
                    self.event(event)
                    errors.append('API %s ended with exception: %s %s' % (api, str(e), traceback.format_exc()))
        # TODO this should be for tests, in production these relations should not be sent out
        agent_proxy.send_parked_relations()
        if len(errors) > 0:
            raise Exception('get_topology gave following exceptions: %s' % ', '.join(errors))

        self.stop_snapshot()

    def get_topology_update(self, instance_info, aws_client):
        agent_proxy = AgentProxy(self, instance_info.role_arn)
        listen_for = ResourceRegistry.CLOUDTRAIL
        for region in instance_info.regions:
            session = aws_client.get_session(instance_info.role_arn, region)
            client = session.client('cloudtrail')
            location = location_info(self.get_account_id(instance_info), session.region_name)
            agent_proxy.location = copy.deepcopy(location)
            stop = False
            for pg in client.get_paginator('lookup_events').paginate(
                LookupAttributes=[
                    {
                        'AttributeKey': 'ReadOnly',
                        'AttributeValue': 'false'
                    }
                ],
            ):
                # TODO collecting should happen first, then processing (to prevent duplication)
                for itm in pg.get('Events') or []:
                    rec = json.loads(itm['CloudTrailEvent'])
                    event_date = dateutil.parser.isoparse(rec['eventTime'])
                    delta = datetime.utcnow().replace(tzinfo=pytz.utc) - event_date
                    if delta.total_seconds() > 60*60*24*5:
                        stop = True
                        break
                    if listen_for.get(rec['eventSource']):
                        event_name = rec.get('eventName')
                        event_class = listen_for[rec['eventSource']].get(event_name)
                        if event_class:
                            if not isinstance(event_class, bool) and issubclass(event_class, Model):
                                event = event_class(rec, strict=False)
                                event.validate()
                                if event.process:
                                    event.process(event_name, session, location, agent_proxy)
                            else:
                                print('should interpret: ' + rec['eventName'] + '-' + rec['eventSource'])
                                print(rec)
                if stop:
                    break
        self.delete_ids += agent_proxy.delete_ids


class AgentProxy(object):
    def __init__(self, agent, role_name):
        self.agent = agent
        self.location = {}
        self.delete_ids = []
        self.components_seen = set()
        self.parked_relations = []
        self.role_name = role_name

    def component(self, id, type, data):
        self.components_seen.add(id)
        data.update(self.location)
        self.agent.component(id, type, correct_tags(capitalize_keys(data)))
        for i in range(len(self.parked_relations)-1, 0, -1):
            relation = self.parked_relations[i]
            if relation['source_id'] == id and relation['target_id'] in self.components_seen:
                self.agent.relation(relation['source_id'], relation['target_id'], relation['type'], relation['data'])
                self.parked_relations.remove(relation)
            if relation['target_id'] == id and relation['source_id'] in self.components_seen:
                self.agent.relation(relation['source_id'], relation['target_id'], relation['type'], relation['data'])
                self.parked_relations.remove(relation)

    def relation(self, source_id, target_id, type, data):
        if source_id in self.components_seen and target_id in self.components_seen:
            self.agent.relation(source_id, target_id, type, data)
        else:
            self.parked_relations.append({
                'type': type,
                'source_id': source_id,
                'target_id': target_id,
                'data': data
            })

    def send_parked_relations(self):
        for relation in self.parked_relations:
            self.agent.relation(relation['source_id'], relation['target_id'], relation['type'], relation['data'])

    def event(self, event):
        self.agent.event(event)

    def delete(self, id):
        self.delete_ids.append(id)

    def warning(self, error, **kwargs):
        # TODO here we aggregate errors smartly to report back to StackState in the end
        print("ERROR ", error)
        print("KWARGS", kwargs)

    def create_arn(self, type, resource_id=''):
        func = type_arn.get(type)
        if func:
            return func(
                region=self.location['Location']['AwsRegion'],
                account_id=self.location['Location']['AwsAccount'],
                resource_id=resource_id
            )
        return "UNSUPPORTED_ARN-" + type + "-" + resource_id

    def create_security_group_relations(self, resource_id, resource_data, security_group_field='SecurityGroups'):
        if resource_data.get(security_group_field):
            for security_group_id in resource_data[security_group_field]:
                self.relation(resource_id, security_group_id, 'uses service', {})


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
            if error.response['Error']['Code'] == 'AccessDenied':
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
