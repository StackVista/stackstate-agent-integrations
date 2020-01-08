# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import datetime
import json
import logging

import boto3

from stackstate_checks.base import AgentCheck, TopologyInstance
from botocore.config import Config

DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)


def get_account_id():
    return boto3.client('sts', config=DEFAULT_BOTO_CONFIG).get_caller_identity().get('Account')


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
        self.log.info('Check')
        region = get_current_region()
        self.log.info(region)
        traces = self.get_xray_traces(region)

    def get_xray_traces(self, region):
        session = boto3.Session(profile_name='sandbox')
        client = session.client('xray', region_name=region, config=DEFAULT_BOTO_CONFIG)
        self.log.info(boto3.session.Session().profile_name)

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
                self.log.info('{} spans in trace {}'.format(len(trace), xray_trace['Id']))
                traces.append(trace)
        self.log.info('{} traces'.format(len(traces)))
        return traces

    def generate_spans(self, segments, service, trace_id=None):
        spans = []
        for segment in segments:
            start = datetime.datetime.utcfromtimestamp(segment['start_time'])
            end = datetime.datetime.utcfromtimestamp(segment['end_time'])
            if not trace_id:
                trace_id = segment['trace_id']

            try:
                resource_name = segment['resource_arn']
            except KeyError:
                try:
                    resource_name = segment['aws']['function_arn']
                except KeyError:
                    try:
                        resource_name = segment['aws']['operation']
                    except KeyError:
                        resource_name = segment['name']

            span = {
                'trace_id': trace_id,
                'span_id': segment['id'],
                'name': segment['name'],
                'resource': resource_name,
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
