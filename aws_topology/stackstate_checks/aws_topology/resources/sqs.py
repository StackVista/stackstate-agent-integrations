from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector
import re


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    match_string = r"^https:\/\/sqs.[a-z]{2}-([a-z]*-){1,2}\d\.amazonaws.com\/\d{12}\/.+$"
    if re.match(match_string, resource_id):
        return arn(
            resource='sqs',
            region=resource_id.split('.', 2)[1],
            account_id=resource_id.rsplit('/', 2)[-2],
            resource_id=resource_id.rsplit('/', 1)[-1],
        )
    else:
        raise ValueError("SQS URL {} does not match expected regular expression {}".format(resource_id, match_string))


class SqsCollector(RegisteredResourceCollector):
    API = "sqs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sqs"
    CLOUDFORMATION_TYPE = 'AWS::SQS::Queue'

    def process_all(self, filter=None):
        for queue_url in self.client.list_queues().get('QueueUrls', []):
            self.process_queue(queue_url)

    def process_queue(self, queue_url):
        queue_data_raw = self.client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        ).get('Attributes', {})
        queue_data = make_valid_data(queue_data_raw)
        queue_arn = queue_data.get('QueueArn')
        queue_name = queue_arn.rsplit(':', 1)[-1]
        queue_data['Tags'] = self.client.list_queue_tags(QueueUrl=queue_url).get('Tags')
        queue_data['URN'] = [queue_url]
        queue_data['Name'] = queue_name
        queue_data['QueueUrl'] = queue_url
        queue_name = queue_url.rsplit('/', 1)[-1]
        queue_data.update(with_dimensions([{'key': 'QueueName', 'value': queue_name}]))

        self.emit_component(queue_arn, self.COMPONENT_TYPE, queue_data)

    EVENT_SOURCE = "sqs.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            'event_name': 'CreateQueue',
            'path': 'responseElements.queueUrl',
            'processor': process_queue
        },
        {
            'event_name': 'DeleteQueue',
            'path': 'requestParameters.queueUrl',
            'processor': RegisteredResourceCollector.process_delete_by_name
        },
        {
            'event_name': 'AddPermission',
        },
        {
            'event_name': 'RemovePermission',
        },
        {
            'event_name': 'SetQueueAttributes',
            'path': 'requestParameters.queueUrl',
            'processor': process_queue
        },
        {
            'event_name': 'TagQueue',
            'path': 'requestParameters.queueUrl',
            'processor': process_queue
        },
        {
            'event_name': 'UntagQueue',
            'path': 'requestParameters.queueUrl',
            'processor': process_queue
        },
        {
            'event_name': 'PurgeQueue'
        }
    ]
