# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import json
import time
import logging
import sys
import uuid
from six import text_type
from datetime import datetime, timedelta

import boto3
import flatten_dict
import requests
from botocore.config import Config
from schematics import Model
from schematics.types import IntType, StringType, ModelType, DateTimeType


from stackstate_checks.base import AgentCheck, TopologyInstance, is_affirmative
from stackstate_checks.utils.common import to_string

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

TRACES_API_ENDPOINT = 'http://localhost:8126/v0.3/traces'
# number of hours
MAX_TRACE_HISTORY_LIMIT = 3
# number of minutes
MAX_TRACE_HISTORY_BATCH_SIZE = 5


class State(Model):
    last_processed_timestamp = DateTimeType(required=True)


class Instance(Model):
    aws_access_key_id = StringType(required=True)
    aws_secret_access_key = StringType(required=True)
    region = StringType(required=True)
    role_arn = StringType()
    max_trace_history_limit = IntType(default=MAX_TRACE_HISTORY_LIMIT)
    max_trace_history_batch_size = IntType(default=MAX_TRACE_HISTORY_BATCH_SIZE)
    state = ModelType(State)


class AwsCheck(AgentCheck):
    """Converts AWS X-Ray traces and sends them to Trace Agent."""
    INSTANCE_TYPE = 'aws'
    SERVICE_CHECK_CONNECT_NAME = 'aws_xray.can_connect'
    SERVICE_CHECK_EXECUTE_NAME = 'aws_xray.can_execute'
    INSTANCE_SCHEMA = Instance

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
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
            aws_client = AwsClient(instance)
            self.region = aws_client.region
            self.account_id = aws_client.get_account_id()
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.OK, tags=self.tags)
        except Exception as e:
            msg = 'AWS connection failed: {}'.format(e)
            self.log.error(msg)
            # set self.account_id so that we can still identify this instance if something went wrong
            aws_access_key_id = instance.aws_access_key_id
            role_arn = instance.role_arn
            # account_id is used in topology instance url, so we recover and set the role_arn or aws_access_key_id as
            # the account_id so we can map the service_check in StackState
            if role_arn:
                self.account_id = to_string(role_arn)
            elif aws_access_key_id:
                self.account_id = to_string(aws_access_key_id)
            else:
                self.account_id = "unknown-instance"
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.CRITICAL, tags=[])
            raise e

        try:
            # empty memory cache
            self.trace_ids = {}
            self.arns = {}
            self._process_xray_traces(aws_client, instance)
            self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.OK, tags=self.tags)
        except Exception as e:
            msg = 'AWS check failed: {}'.format(e)
            self.log.error(msg)
            self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.CRITICAL, message=msg, tags=self.tags)
            raise e

    def _process_xray_traces(self, aws_client, instance):
        """
        Process XRAY Traces in following process on each check run
        fetch_batch -> process_batch -> send_batch -> commit_state
        @param
        aws_client: AWS Client
        instance: Instance schema of this check
        @return
        None
        """
        start_time, end_time = self.get_start_end_time_trace(instance)
        xray_traces_batch = self.fetch_batch_traces(aws_client, start_time, end_time)
        traces = self.process_batch_traces(xray_traces_batch)
        self.send_batch_traces(traces)
        instance.state.last_processed_timestamp = end_time

    def process_batch_traces(self, xray_traces_batch):
        """
        Process incoming batch traces
        @param
        xray_traces_batch: List of xray traces batch from AWS API
        @return
        Returns the list of formatted traces in Span format required by Trace API
        """
        traces = []
        for xray_traces in xray_traces_batch:
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self._generate_spans(segment_documents))
                traces.append(trace)
                self.log.debug('Converted %s x-ray segments to traces.', len(trace))
        self.log.debug('Collected total %s traces.', len(traces))
        return traces

    def fetch_batch_traces(self, aws_client, start_time, end_time):
        """
        Fetch the batch of traces from AWS with start and end time
        @param
        aws_client: AWS Client
        start_time: StartTime parameter for API to collect trace from
        end_time: EndTime parameter for API to collect trace to
        @return
        Returns the list of traces from AWS
        """
        self.log.debug("Collecting traces from {} to {}".format(start_time, end_time))
        xray_client = aws_client.get_boto3_client('xray')
        operation_params = {
            'StartTime': start_time,
            'EndTime': end_time
        }
        traces = []
        for page in xray_client.get_paginator('get_trace_summaries').paginate(**operation_params):
            for trace_summary in page['TraceSummaries']:
                traces.append(xray_client.batch_get_traces(TraceIds=[trace_summary['Id']]))
        return traces

    @staticmethod
    def _current_time():
        """
        This method is mocked for testing. Do not change its behavior
        @return: current time in utc
        """
        return datetime.utcnow()

    def get_start_end_time_trace(self, instance):
        """
        Calculate start and end time for collecting the traces
        Case 1: Normal Start up
         - Start up, no state.
         - Fetch from MAX_TRACE_HISTORY_LIMIT (start time) in batches of MAX_TRACE_HISTORY_BATCH_SIZE (end time).
        Case 2: Behind less than MAX_TRACE_HISTORY_LIMIT
         - Start up, state < MAX_TRACE_HISTORY_LIMIT.
         - If MAX_TRACE_HISTORY_BATCH_SIZE < state < MAX_TRACE_HISTORY_LIMIT
         - Fetch from state(start time) in batches of MAX_TRACE_HISTORY_BATCH_SIZE (end time)
        Case 3: Behind more than MAX_TRACE_HISTORY_LIMIT
         - Start up, state > MAX_TRACE_HISTORY_LIMIT.
         - Reset state to current utc - MAX_TRACE_HISTORY_LIMIT.
         - Fetch from state (start time) in batches of MAX_TRACE_HISTORY_BATCH_SIZE (end time).

        @param
        instance: Instance schema of the check
        @return
        Returns the start time and end time
        """
        if not instance.state:
            # reason to add 1 min is we might lag few seconds till we reach the comparison for normal start
            trace_end_timestamp = self._current_time() - timedelta(hours=instance.max_trace_history_limit) \
                                  + timedelta(minutes=1)
            self.log.info('Creating default start time for the trace : %s', trace_end_timestamp)
            instance.state = State({'last_processed_timestamp': trace_end_timestamp})
        start_time = instance.state.last_processed_timestamp
        diff_time = self._current_time() - start_time
        # case 1 & case 2: Normal Startup | Behind less than MAX_TRACE_HISTORY_LIMIT
        if timedelta(minutes=instance.max_trace_history_batch_size) <= diff_time <= \
                timedelta(hours=instance.max_trace_history_limit):
            end_time = start_time + timedelta(minutes=instance.max_trace_history_batch_size)
            self.log.info("Catching up from {} to {}".format(start_time, end_time))
        # case 3: Behind more than MAX_TRACE_HISTORY_LIMIT
        elif diff_time > timedelta(hours=instance.max_trace_history_limit):
            # reset the start time to utc - 3 hours
            self.log.info("Lagging behind more than defined threshold value of MAX_TRACE_HISTORY_LIMIT : {}hrs. "
                          "Resetting now....".format(instance.max_trace_history_limit))
            start_time = self._current_time() - timedelta(hours=instance.max_trace_history_limit)
            end_time = start_time + timedelta(minutes=instance.max_trace_history_batch_size)
        # when not lagging behind
        else:
            self.log.info("Catching up complete till {} and will continue normally"
                          .format(start_time))
            # we don't like to go in future so we always fetch from state to current time if no lagging behind
            end_time = self._current_time()
        return start_time, end_time

    def _generate_spans(self, segments, trace_id=None, parent_id=None, kind="client"):
        """
        Translates X-Ray trace to StackState trace.
        @param
        segments: Segment Documents from AWS Trace API
        trace_id: 64bit unsigned integer Trace ID
        parent_id: Segment ID for the parent span
        kind: Type of span default to Client
        @return
        Returns the list of spans formatted in Trace-Agent defined structure
        """
        spans = []

        for segment in segments:
            span_id = int(segment['id'], 16)
            start = datetime.utcfromtimestamp(segment['start_time'])
            try:
                end = datetime.utcfromtimestamp(segment['end_time'])
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
            # STAC-13020: we decided to make all the spans from aws-xray as CLIENT to produce metrics
            # otherwise receiver won't produce any metrics if the kind is INTERNAL
            flat_segment["span.kind"] = kind
            flat_segment["span.serviceType"] = "xray"
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

            # Check if there is error in X-Ray Trace and split error on response code for trace metrics
            span = process_http_error(span, segment)

            spans.append(span)

            if 'subsegments' in segment.keys():
                # use kind as "internal" for the subsegments
                spans.extend(self._generate_spans(segment['subsegments'], trace_id, span_id, kind="internal"))

        return spans

    def _convert_trace_id(self, aws_trace_id):
        """
        Converts Amazon X-Ray trace_id to 64bit unsigned integer.
        @param
        aws_trace_id: Segment Trace ID from AWS Trace API
        @return
        Returns the 64bit unsigned integer
        """
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

    def send_batch_traces(self, traces):
        """
        Sends traces payload to Traces Agent.
        @param
        traces: the payload to be sent to TraceAPI
        """
        headers = {'Content-Type': 'application/json'}
        if traces:
            start = time.time()
            self.log.info("Size of traces data to be sent is {} bytes".format(sys.getsizeof(traces)))
            requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)
            self.log.info("Time took to send the data is: {}s".format(time.time()-start))


class AwsClient:
    def __init__(self, instance):
        self.log = logging.getLogger(__name__)
        aws_access_key_id = instance.aws_access_key_id
        aws_secret_access_key = instance.aws_secret_access_key
        role_arn = instance.role_arn
        self.region = instance.region
        self.aws_session_token = None
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
        return self.get_boto3_client('sts').get_caller_identity().get('Account')

    def get_boto3_client(self, service_name):
        return boto3.client(service_name, region_name=self.region, config=DEFAULT_BOTO3_CONFIG,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key,
                            aws_session_token=self.aws_session_token)


def flatten_segment(segment):
    """
    Flatten the nested disctionary object into root dictionary
    @param
    segment: The Trace segment which has to be flatten
    kind: Span Kind
    @return
    Returns the flatten segment with additional fields
    """
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
                # sometimes we can receive unicode data for some of the field
                if isinstance(value, text_type):
                    flat_segment[key] = to_string(value)
                else:
                    flat_segment[key] = str(value)
    return flat_segment


def process_http_error(span, segment):
    """
    Process the span on different error code
    @param
    span: The span in which error code has to be sent
    segment: The segment from which error code has to be processed
    @return
    Returns the span processed with error codes
    """
    error = segment.get('fault') or segment.get('throttle') or segment.get('error')
    if is_affirmative(error):
        # this is always required to produce the trace error metrics
        span['error'] = 1
        meta = span.get('meta')
        if meta:
            status_code = meta.get("http.response.status")
            if status_code:
                if 400 <= int(status_code) < 500:
                    meta["span.errorClass"] = "4xx"
                elif int(status_code) >= 500:
                    meta["span.errorClass"] = "5xx"
                span['meta'] = meta
    return span


def dot_reducer(key1, key2):
    """
    Format pair of keys into key1.key2 format
    @param
    key1: first key
    key2: second key
    @return
    Returns the keys in format key1.key2
    """
    if key1 is None:
        return key2
    else:
        return '{}.{}'.format(key1, key2)
