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


class AwsCheck(AgentCheck):
    INSTANCE_TYPE = 'aws'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.log.setLevel(logging.INFO)
        self.trace_ids = {}
        self.region = None
        self.account_id = None

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        aws_client = AwsClient(instance)
        self.region = aws_client.region
        self.account_id = aws_client.get_account_id()

        traces = []
        xray_traces_batch = aws_client.get_xray_traces()
        for xray_traces in xray_traces_batch:
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self._generate_spans(segment_documents))
                traces.append(trace)

        headers = {'Content-Type': 'application/json'}
        requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)

    def _generate_spans(self, segments, trace_id=None, parent_id=None):
        """Translates X-Ray trace to StackState trace."""
        spans = []
        pp = PrettyPrinter(indent=2)

        for segment in segments:
            pp.pprint(segment)

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

            # find resource type
            try:
                resource_type = segment['origin']
            except KeyError:
                resource_type = segment['name']

            # find service name
            try:
                service_name = segment['resource_arn']
            except KeyError:
                try:
                    service_name = segment['aws']['function_arn']
                except KeyError:
                    service_name = segment['name']

            if 'arn:' not in service_name:
                arn = self._generate_arn(resource_type, segment)
                if arn:
                    service_name = arn

            try:
                span_parent_id = int(segment['parent_id'], 16)
            except KeyError:
                span_parent_id = parent_id

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

            # flatten_all([segment])

            self.log.debug(span)
            pp.pprint(span)
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

    def _generate_arn(self, resource_type, segment):
        """Generates ARN on one of the following patterns:
        arn:partition:service:region:account-id:resource-id
        arn:partition:service:region:account-id:resource-type/resource-id
        arn:partition:service:region:account-id:resource-type:resource-id
        """
        arn = None

        service = None
        resource_format = None
        aws_key = None
        resource = None

        if resource_type in ['AWS::Lambda::Function', 'AWS::Lambda', 'Lambda']:
            service = 'lambda'
            resource_format = 'function:{}'
            aws_key = 'function_name'
        elif resource_type == 'AWS::Kinesis::Stream':
            service = 'kinesis_stream'
        elif resource_type == 'AWS::S3::Bucket':
            service = 's3'
        elif resource_type == 'AWS::RDS::DBInstance':
            service = 'rds'
        elif resource_type == 'AWS::SNS::Topic':
            service = 'sns'
        elif resource_type == 'AWS::SQS::Queue':
            service = 'sqs'
        elif resource_type in ['AWS::DynamoDB::Table', 'AWS::DynamoDB', 'DynamoDB']:
            service = 'dynamodb'
            resource_format = 'table/{}'
            aws_key = 'table_name'
        elif resource_type == 'AWS::EC2::Instance':
            service = 'ec2'
        elif resource_type == 'remote':
            service = 'remote'

        if service:
            try:
                resource = resource_format.format(segment['aws'][aws_key])
            except KeyError:
                pass
            if resource:
                arn = 'arn:aws:{0}:{1}:{2}:{3}'.format(service, self.region, self.account_id, resource)
            else:
                arn = segment['aws']['operation']

        return arn


class AwsClient:
    def __init__(self, instance):
        self.aws_session_token = None
        aws_access_key_id = instance.get('aws_access_key_id')
        aws_secret_access_key = instance.get('aws_secret_access_key')
        role_arn = instance.get('role_arn')
        self.region = instance.get('region')

        if aws_secret_access_key and aws_access_key_id and role_arn and self.region:
            sts_client = boto3.client('sts', config=DEFAULT_BOTO3_CONFIG, aws_access_key_id=aws_access_key_id,
                                      aws_secret_access_key=aws_secret_access_key)
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='sts-agent-check')
            self.aws_access_key_id = role['Credentials']['AccessKeyId']
            self.aws_secret_access_key = role['Credentials']['SecretAccessKey']
            self.aws_session_token = role['Credentials']['SessionToken']

    def get_account_id(self):
        return boto3.client('sts', config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=self.aws_session_token).get_caller_identity().get('Account')

    def get_xray_traces(self):
        xray_client = boto3.client('xray', region_name=self.region, config=DEFAULT_BOTO3_CONFIG,
                                   aws_access_key_id=self.aws_access_key_id,
                                   aws_secret_access_key=self.aws_secret_access_key,
                                   aws_session_token=self.aws_session_token)

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
            traces.append(xray_client.batch_get_traces(TraceIds=[trace_summary['Id']]))

        return traces


def dot_reducer(key1, key2):
    if key1 is None:
        return key2
    else:
        return '{}.{}'.format(key1, key2)


def flatten_all(segments):
    for segment in segments:
        if 'subsegments' in segment.keys():
            segment['subsegments'] = flatten_all(segment['subsegments'])
        segment = flatten(segment, dot_reducer)
    return segments
