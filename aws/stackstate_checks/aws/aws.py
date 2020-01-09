# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json
import logging

import boto3
import requests

from stackstate_checks.base import AgentCheck, TopologyInstance
from botocore.config import Config

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)

TRACES_API_ENDPOINT = 'http://localhost:8126/v0.3/traces'


def get_account_id():
    return boto3.client('sts', config=DEFAULT_BOTO3_CONFIG).get_caller_identity().get('Account')


def get_current_region():
    return boto3.session.Session().region_name


class AwsCheck(AgentCheck):
    INSTANCE_TYPE = 'aws'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.account_id = get_account_id()
        self.log.setLevel(logging.INFO)

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        region = get_current_region()
        traces = self.get_xray_traces(region)
        headers = {'Content-Type': 'application/json'}
        requests.put(TRACES_API_ENDPOINT, data=json.dumps(traces), headers=headers)

    def get_xray_traces(self, region):
        session = boto3.Session(profile_name='sandbox')
        client = session.client('xray', region_name=region, config=DEFAULT_BOTO3_CONFIG)

        start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        end_time = datetime.datetime.utcnow()
        operation_params = {'StartTime': start_time, 'EndTime': end_time}
        trace_summaries = []
        traces = []

        for page in client.get_paginator('get_trace_summaries').paginate(**operation_params):
            for trace_summary in page['TraceSummaries']:
                trace_summaries.append(trace_summary)

        for trace_summary in trace_summaries:
            service_name = trace_summary['EntryPoint']['Name']
            xray_traces = client.batch_get_traces(TraceIds=[trace_summary['Id']])
            for xray_trace in xray_traces['Traces']:
                trace = []
                for segment in xray_trace['Segments']:
                    segment_documents = [json.loads(segment['Document'])]
                    trace.extend(self.generate_spans(segment_documents, service_name))
                traces.append(trace)

        return traces

    def generate_spans(self, segments, service, trace_id=None):
        spans = []
        for segment in segments:
            start = datetime.datetime.utcfromtimestamp(segment['start_time'])
            end = datetime.datetime.utcfromtimestamp(segment['end_time'])
            if not trace_id:
                trace_id = segment['trace_id']

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

            span = {
                'trace_id': trace_id,
                'span_id': segment['id'],
                'name': segment['name'],
                'resource': resource,
                'service': service,
                'start': segment['start_time'],
                'duration': str((end - start) / datetime.timedelta(milliseconds=1))
            }

            try:
                span['parent_id'] = segment['parent_id']
            except KeyError:
                # Root of the trace
                pass

            spans.append(span)

            if 'subsegments' in segment.keys():
                spans.extend(self.generate_spans(segment['subsegments'], service, trace_id))

        return spans
