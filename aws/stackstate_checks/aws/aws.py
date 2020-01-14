# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json
import logging
from pprint import PrettyPrinter

import boto3
import requests
import uuid
from botocore.config import Config
from flatten_dict import flatten

from stackstate_checks.base import AgentCheck, TopologyInstance

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

TRACES_API_ENDPOINT = 'http://localhost:8126/v0.3/traces'


def get_current_region():
    return boto3.session.Session().region_name


class AwsCheck(AgentCheck):
    INSTANCE_TYPE = 'aws'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.log.setLevel(logging.INFO)
        self.trace_ids = {}
        self.account_id = None
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.region = None

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        self.aws_access_key_id = instance.get('aws_access_key_id')
        self.aws_secret_access_key = instance.get('aws_secret_access_key')
        role_arn = instance.get('role_arn')
        self.region = instance.get('region')
        if self.aws_secret_access_key and self.aws_access_key_id and role_arn and self.region:
            sts_client = boto3.client('sts', config=DEFAULT_BOTO3_CONFIG, aws_access_key_id=self.aws_access_key_id,
                                      aws_secret_access_key=self.aws_secret_access_key)
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='xray-client')
            self.aws_access_key_id = role['Credentials']['AccessKeyId']
            self.aws_secret_access_key = role['Credentials']['SecretAccessKey']
            session_token = role['Credentials']['SessionToken']

            self.account_id = self._get_account_id(session_token)

            traces = self._get_xray_traces(session_token)

            headers = {'Content-Type': 'application/json'}
            requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)
        else:
            # TODO: agent service check
            pass

    def _get_xray_traces(self, session_token):
        xray_client = boto3.client('xray', region_name=self.region, config=DEFAULT_BOTO3_CONFIG,
                                   aws_access_key_id=self.aws_access_key_id,
                                   aws_secret_access_key=self.aws_secret_access_key,
                                   aws_session_token=session_token)

        # TODO: for development timedelta is 1 hour, it should be 1 minute
        start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        end_time = datetime.datetime.utcnow()
        operation_params = {'StartTime': start_time, 'EndTime': end_time}
        trace_summaries = []
        traces = []

        for page in xray_client.get_paginator('get_trace_summaries').paginate(**operation_params):
            for trace_summary in page['TraceSummaries']:
                trace_summaries.append(trace_summary)

        for trace_summary in trace_summaries:
            xray_traces = xray_client.batch_get_traces(TraceIds=[trace_summary['Id']])
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self._generate_spans(segment_documents))
                traces.append(trace)

        return traces

    def _generate_spans(self, segments, trace_id=None, parent_id=None):
        """Translates X-Ray trace to StackState trace."""
        spans = []

        for segment in segments:
            span_id = int(segment['id'], 16)
            start = datetime.datetime.utcfromtimestamp(segment['start_time'])
            try:
                end = datetime.datetime.utcfromtimestamp(segment['end_time'])
            except KeyError:
                # segment still in progress, we skip it
                continue
            duration = (end - start).total_seconds()

            if not trace_id:
                trace_id = self._convert_trace_id(segment['trace_id'])

            # find service name
            try:
                service_name = segment['resource_arn']
            except KeyError:
                try:
                    service_name = segment['aws']['function_arn']
                except KeyError:
                    try:
                        service_name = segment['aws']['operation']
                    except KeyError:
                        service_name = segment['name']

            # find resource type
            try:
                resource_type = segment['origin']
            except KeyError:
                resource_type = segment['name']

            try:
                span_parent_id = int(segment['parent_id'], 16)
            except KeyError:
                span_parent_id = parent_id

            # fix service name
            if 'arn:' not in service_name:
                # arn:partition:service:region:account-id:resource-id
                # arn:partition:service:region:account-id:resource-type/resource-id
                # arn:partition:service:region:account-id:resource-type:resource-id
                service, resource_format, aws_key = get_service(resource_type)
                resource = None
                if service:
                    try:
                        resource = resource_format.format(segment['aws'][aws_key])
                    except KeyError:
                        pass
                    if resource:
                        service_name = 'arn:aws:{0}:{1}:{2}:{3}'.format(service, self.region, self.account_id, resource)

            # times format is nanoseconds from the unix epoch
            span = {
                'trace_id': trace_id,
                'span_id': span_id,
                'name': segment['name'],
                'resource': resource_type,
                'service': service_name,
                'start': int(segment['start_time'] * 1000000000),
                'duration': int(duration * 1000000000),
                'parent_id': span_parent_id
            }

            pp = PrettyPrinter(indent=2)
            pp.pprint(flatten(segment, reducer=dot_reducer))

            self.log.debug(span)
            # TODO: filter traces based on resource type
            spans.append(span)

            if 'subsegments' in segment.keys():
                spans.extend(self._generate_spans(segment['subsegments'], trace_id, span_id))

        return spans

    def _convert_trace_id(self, aws_trace_id):
        """Converts Amazon X-Ray trace_id to 64bit unsigned integer."""
        try:
            trace_id = self.trace_ids[aws_trace_id]
        except KeyError:
            trace_id = uuid.uuid4().int & (1 << 64) - 1
            self.trace_ids[aws_trace_id] = trace_id
        return trace_id

    def _get_account_id(self, aws_session_token):
        return boto3.client('sts', config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=aws_session_token).get_caller_identity().get('Account')


def get_service(resource_type):
    if resource_type in ['AWS::Lambda::Function', 'AWS::Lambda', 'Lambda']:
        return 'lambda', 'function:{}', 'function_name'
    elif resource_type == 'AWS::Kinesis::Stream':
        return 'kinesis_stream', None, None
    elif resource_type == 'AWS::S3::Bucket':
        return 's3', None, None
    elif resource_type == 'AWS::RDS::DBInstance':
        return 'rds', None, None
    elif resource_type == 'AWS::SNS::Topic':
        return 'sns', None, None
    elif resource_type == 'AWS::SQS::Queue':
        return 'sqs', None, None
    elif resource_type in ['AWS::DynamoDB::Table', 'AWS::DynamoDB', 'DynamoDB']:
        return 'dynamodb', 'table/{}', 'table_name'
    elif resource_type == 'AWS::EC2::Instance':
        return 'ec2', None, None
    elif resource_type == 'remote':
        return 'remote', None, None
    else:
        return None, None, None


def dot_reducer(key1, key2):
    if key1 is None:
        return key2
    else:
        return '{}.{}'.format(key1, key2)
