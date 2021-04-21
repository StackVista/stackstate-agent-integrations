from .utils import make_valid_data
from .registry import RegisteredResourceCollector


class LambdaeventsourcemappingCollector(RegisteredResourceCollector):
    API = "lambda"
    COMPONENT_TYPE = "aws.lambda.event_source_mapping"

    def process_all(self):
        for page in self.client.get_paginator('list_event_source_mappings').paginate():
            for event_source_raw in page.get('EventSourceMappings') or []:
                event_source = make_valid_data(event_source_raw)
                if event_source['State'] == 'Enabled':
                    self.process_event_source(event_source)

    def process_event_source(self, event_source):
        source_id = event_source['EventSourceArn']
        target_id = event_source['FunctionArn']
        # Swapping source/target: StackState models dependencies, not data flow
        self.agent.relation(target_id, source_id, 'uses service', event_source)
