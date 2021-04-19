# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .registry import ResourceRegistry
import time
import traceback


def location_info(account_id, region):
    return {'Location': {'AwsAccount': account_id, 'AwsRegion': region}}


class AWSTopologyScraperMixin(object):
    # pylint: disable=E1101
    # This class is not supposed to be used by itself, it provides scraping behavior but
    # need to be within a check in the end

    def __init__(self, *args, **kwargs):
        # Initialize AgentCheck's base class
        super(AWSTopologyScraperMixin, self).__init__(*args, **kwargs)

    def get_topology(self, instance_info, aws_client):
        """Gets AWS Topology returns them in Agent format."""
        self.start_snapshot()

        self.memory_data = {}  # name -> arn for cloudformation
        errors = []
        self.delete_ids = []
        registry = ResourceRegistry.get_registry()
        keys = [key for key in registry.keys()]
        if instance_info.apis_to_run is not None:
            keys = [api.split('|')[0] for api in instance_info.apis_to_run]
        # move cloudformation to the end
        if 'cloudformation' in keys:
            keys.append(keys.pop(keys.index('cloudformation')))
        for api in keys:
            global_api = api.startswith('route53')
            client = aws_client.get_boto3_client(api, region='us-east-1' if global_api else None)
            location = location_info(instance_info.account_id, 'us-east-1' if global_api else instance_info.region)
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
