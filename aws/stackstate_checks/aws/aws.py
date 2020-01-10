# (C) StackState, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json
import logging

import boto3
import requests
import uuid
from botocore.config import Config

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
        self.account_id = None
        self.log.setLevel(logging.INFO)
        self.trace_ids = {}

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        aws_access_key_id = instance.get('aws_access_key_id')
        aws_secret_access_key = instance.get('aws_secret_access_key')
        role_arn = instance.get('role_arn')
        region = instance.get('region')
        if aws_secret_access_key and aws_access_key_id and role_arn and region:
            sts_client = boto3.client('sts', config=DEFAULT_BOTO3_CONFIG, aws_access_key_id=aws_access_key_id,
                                      aws_secret_access_key=aws_secret_access_key)
            role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName='xray-client')
            traces = self._get_xray_traces(role, region)

            headers = {'Content-Type': 'application/json'}
            requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)
        else:
            # TODO: agent service check
            pass

    def _get_xray_traces(self, role, region):
        access_key_id = role['Credentials']['AccessKeyId']
        secret_access_key = role['Credentials']['SecretAccessKey']
        session_token = role['Credentials']['SessionToken']
        xray_client = boto3.client('xray', region_name=region, config=DEFAULT_BOTO3_CONFIG,
                                   aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
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
            service_name = trace_summary['EntryPoint']['Name']
            xray_traces = xray_client.batch_get_traces(TraceIds=[trace_summary['Id']])
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self._generate_spans(segment_documents))
                traces.append(trace)

        return traces

    def _generate_spans(self, segments, trace_id=None):
        """Translates X-Ray trace to StackState trace."""
        spans = []
        for segment in segments:
            start = datetime.datetime.utcfromtimestamp(segment['start_time'])
            try:
                end = datetime.datetime.utcfromtimestamp(segment['end_time'])
            except KeyError:
                # segment still in progress, we skip it
                continue
            duration = (end - start).total_seconds()

            if not trace_id:
                trace_id = self._convert_trace_id(segment['trace_id'])

            # TODO: filter traces based on resource type

            # find resource name
            try:
                resource = segment['resource_arn']
            except KeyError:
                try:
                    resource = segment['aws']['function_arn']
                except KeyError:
                    try:
                        resource = segment['aws']['operation']
                    except KeyError:
                        resource = segment['name']

            # find service name
            try:
                service = segment['origin']
            except KeyError:
                service = segment['name']

            # times format is nanoseconds from the unix epoch
            span = {
                'trace_id': trace_id,
                'span_id': int(segment['id'], 16),
                'name': segment['name'],
                'resource': resource,
                'service': service,
                'start': int(segment['start_time'] * 1000000000),
                'duration': int(duration * 1000000000)
            }

            try:
                span['parent_id'] = int(segment['parent_id'], 16)
            except KeyError:
                # Root of the trace, so no parent
                pass

            spans.append(span)

            if 'subsegments' in segment.keys():
                spans.extend(self._generate_spans(segment['subsegments'], trace_id))

        return spans

    def _convert_trace_id(self, aws_trace_id):
        """Converts Amazon X-Ray trace_id to 64bit unsigned integer."""
        try:
            trace_id = self.trace_ids[aws_trace_id]
        except KeyError:
            trace_id = uuid.uuid4().int & (1 << 64) - 1
            self.trace_ids[aws_trace_id] = trace_id
        return trace_id
