# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json
import logging
import os
import tempfile
import uuid

import boto3
import flatten_dict
import requests
from botocore.config import Config

from stackstate_checks.base import AgentCheck, TopologyInstance, is_affirmative

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

TRACES_API_ENDPOINT = 'http://localhost:8126/v0.3/traces'

DEFAULT_COLLECTION_INTERVAL = 60


class AwsCheck(AgentCheck):
    """Converts AWS X-Ray traces and sends them to Trace Agent."""
    INSTANCE_TYPE = 'aws'
    SERVICE_CHECK_CONNECT_NAME = 'aws_xray.can_connect'
    SERVICE_CHECK_EXECUTE_NAME = 'aws_xray.can_execute'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.log.setLevel(logging.INFO)
        self.trace_ids = {}
        self.region = None
        # default the account id to the role_arn, this will be replaced by the account id after a successful login
        self.account_id = self.instance.get('role_arn', 'unknown-instance')
        self.tags = None
        self.arns = {}

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        try:
            aws_client = AwsClient(instance, self.init_config)
            self.region = aws_client.region
            self.account_id = aws_client.get_account_id()
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.OK, tags=self.tags)
        except Exception as e:
            msg = 'AWS connection failed: {}'.format(e)
            self.log.error(msg)
            # set self.account_id so that we can still identify this instance if something went wrong
            aws_access_key_id = instance.get('aws_access_key_id')
            role_arn = instance.get('role_arn')
            # account_id is used in topology instance url, so we recover and set the role_arn or aws_access_key_id as
            # the account_id so we can map the service_check in StackState
            if role_arn:
                self.account_id = role_arn
            elif aws_access_key_id:
                self.account_id = aws_access_key_id
            else:
                self.account_id = "unknown-instance"
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.CRITICAL, message=msg, tags=self.tags)
            return

        try:
            traces = self._process_xray_traces(aws_client)

            if traces:
                self._send_payload(traces)

            aws_client.write_cache_file()
            self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.OK, tags=self.tags)
        except Exception as e:
            msg = 'AWS check failed: {}'.format(e)
            self.log.error(msg)
            self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.CRITICAL, message=msg, tags=self.tags)

    def _process_xray_traces(self, aws_client):
        """Gets AWS X-Ray traces returns them in Trace Agent format."""
        traces = []
        xray_traces_batch = aws_client.get_xray_traces()
        self.log.info('XXXXX started processing xray traces.')
        for xray_traces in xray_traces_batch:
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self._generate_spans(segment_documents))
                self.log.info('XXXXX appended %s traces', len(trace))
                traces.append(trace)
        self.log.info('XXXXX total %s traces.', len(traces))
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

            resource_type = segment.get('origin', segment.get('name'))

            try:
                parent_span_id = int(segment['parent_id'], 16)
            except KeyError:
                parent_span_id = parent_id

            # we use Amazon ARN for service name
            service_name = segment.get('resource_arn', segment.get('name'))
            if 'arn:' not in service_name:
                arn = self._generate_arn(resource_type, segment, span_id, parent_span_id)
                if arn:
                    service_name = arn

            flat_segment = flatten_segment(segment)

            # times format is the unix epoch in nanoseconds
            span = {
                'trace_id': trace_id,
                'span_id': span_id,
                'name': segment['name'],
                'resource': resource_type,
                'service': service_name,
                'start': int(segment['start_time'] * 1000000000),
                'duration': int(duration * 1000000000),
                'parent_id': parent_span_id,
                'meta': flat_segment
            }

            # Check if there is error in X-Ray Trace
            if is_affirmative(segment.get('error')):
                span['error'] = 1

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

    def _generate_arn(self, resource_type, segment, span_id, parent_span_id):
        """Generates ARN based on one of the following patterns:
        arn:partition:service:region:account-id:resource-id
        arn:partition:service:region:account-id:resource-type/resource-id
        arn:partition:service:region:account-id:resource-type:resource-id
        """
        arn = None
        resource = None
        arn_format = None

        if resource_type in ['AWS::Lambda::Function', 'AWS::Lambda', 'Lambda', 'Overhead', 'Initialization',
                             'Invocation']:
            try:
                arn = segment['aws']['function_arn']
            except KeyError:
                arn_format = 'arn:aws:lambda:{0}:{1}:function:{2}'
                try:
                    resource = segment['aws']['function_name']
                except KeyError:
                    arn = segment['aws']['operation']
        elif resource_type == 'AWS::Kinesis::Stream':
            # TODO: finish creating Kinesis stream ARN
            # service = 'kinesis_stream'
            pass
        elif resource_type == 'AWS::S3::Bucket':
            # TODO: finish creating S3 ARN
            # service = 's3'
            pass
        elif resource_type == 'AWS::RDS::DBInstance':
            # TODO: finish creating RDS ARN
            # service = 'rds'
            pass
        elif resource_type == 'AWS::SNS::Topic':
            # TODO: finish creating SNS ARN
            # service = 'sns'
            pass
        elif resource_type == 'AWS::SQS::Queue':
            # TODO: finish creating SQS ARN
            # service = 'sqs'
            pass
        elif resource_type in ['AWS::DynamoDB::Table', 'AWS::DynamoDB', 'DynamoDB']:
            arn_format = 'arn:aws:dynamodb:{0}:{1}:table/{2}'
            try:
                resource = segment['aws']['table_name']
            except KeyError:
                arn = segment['aws']['operation']
        elif resource_type == 'AWS::EC2::Instance':
            arn_format = 'arn:aws:ec2:{0}:{1}:instance/{2}'
            try:
                resource = segment['aws']['ec2']['instance_id']
            except KeyError:
                pass
        else:
            if segment.get('namespace') == 'local':
                try:
                    arn = self.arns[parent_span_id]
                    self.arns[span_id] = arn
                except KeyError:
                    pass

        if resource:
            arn = arn_format.format(self.region, self.account_id, resource)

        if arn:
            self.arns[span_id] = arn

        return arn

    @staticmethod
    def _send_payload(traces):
        """Sends traces payload to Traces Agent."""
        headers = {'Content-Type': 'application/json'}
        requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)


class AwsClient:
    def __init__(self, instance, config):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)

        aws_access_key_id = instance.get('aws_access_key_id')
        aws_secret_access_key = instance.get('aws_secret_access_key')
        role_arn = instance.get('role_arn')
        self.region = instance.get('region')
        self.aws_session_token = None
        self.collection_interval = instance.get('min_collection_interval', DEFAULT_COLLECTION_INTERVAL)
        self.cache_file = config.get('cache_file', os.path.join(tempfile.gettempdir(), 'sts_agent_aws_check_end_time'))
        self.last_end_time = None

        if aws_secret_access_key and aws_access_key_id and role_arn and self.region:
            sts_client = boto3.client('sts', config=DEFAULT_BOTO3_CONFIG, aws_access_key_id=aws_access_key_id,
                                      aws_secret_access_key=aws_secret_access_key)
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='sts-agent-check')
            self.aws_access_key_id = role['Credentials']['AccessKeyId']
            self.aws_secret_access_key = role['Credentials']['SecretAccessKey']
            self.aws_session_token = role['Credentials']['SessionToken']
        else:
            self.aws_access_key_id = aws_access_key_id
            self.aws_secret_access_key = aws_secret_access_key

    def get_account_id(self):
        return self._get_boto3_client('sts').get_caller_identity().get('Account')

    def get_xray_traces(self):
        xray_client = self._get_boto3_client('xray')

        start_time = self._get_last_request_end_time()
        traces = []

        operation_params = {
            'StartTime': start_time,
            'EndTime': datetime.datetime.utcnow()
        }
        trace_summaries = []
        traces = []

        for page in xray_client.get_paginator('get_trace_summaries').paginate(**operation_params):
            for trace_summary in page['TraceSummaries']:
                trace_summaries.append(trace_summary)

        for trace_summary in trace_summaries:
            traces.append(xray_client.batch_get_traces(TraceIds=[trace_summary['Id']]))

        self.last_end_time = operation_params['EndTime']
        return traces

    def _get_boto3_client(self, service_name):
        return boto3.client(service_name, region_name=self.region, config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=self.aws_session_token)

    def _get_last_request_end_time(self):
        try:
            with open(self.cache_file, 'r') as file:
                last_end_time = file.read()
                start_time = datetime.datetime.utcfromtimestamp(float(last_end_time))
                self.log.info(
                    'Read {}. Start time for X-Ray retrieval period is last retrieval end time: {}'.format(
                        self.cache_file, start_time))
                if datetime.datetime.now() - datetime.timedelta(hours=24) > start_time:
                    start_time = self.default_start_time()
                    self.log.info('Time range cannot be longer than 24 hours. '
                                  'New Start time for X-Ray retrieval period is: {}'.format(start_time))
        except IOError:
            start_time = self.default_start_time()
            self.log.info(
                'Cache file {} not found. Start time for X-Ray retrieval period is: {}'.format(self.cache_file,
                                                                                               start_time))
        return start_time

    def default_start_time(self):
        return datetime.datetime.utcnow() - datetime.timedelta(seconds=self.collection_interval)

    def write_cache_file(self):
        with open(self.cache_file, 'w') as file:
            end_timestamp = (self.last_end_time - datetime.datetime.utcfromtimestamp(0)).total_seconds()
            file.write('{:f}'.format(end_timestamp))
            self.log.info('Writen X-Ray retrieval end time {} to {}'.format(self.last_end_time, self.cache_file))


def flatten_segment(segment):
    flat_segment = flatten_dict.flatten(segment, dot_reducer)
    for key, value in flat_segment.items():
        if key == 'subsegments':
            ids = []
            for sub_segment in flat_segment[key]:
                ids.append(sub_segment['id'])
            flat_segment[key] = ', '.join(ids)
        else:
            if isinstance(value, list):
                flat_segment[key] = ', '.join([str(elem) for elem in value])
            elif not isinstance(value, str):
                flat_segment[key] = str(value)
    return flat_segment


def dot_reducer(key1, key2):
    if key1 is None:
        return key2
    else:
        return '{}.{}'.format(key1, key2)
