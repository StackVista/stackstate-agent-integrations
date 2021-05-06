from .utils import make_valid_data, with_dimensions, CloudTrailEventBase, create_arn as arn
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='sqs', region='', account_id=account_id, resource_id=resource_id)


def get_queue_name_from_url(url):
    return url.rsplit('/', 1)[-1]


class Sqs_CreateQueue(CloudTrailEventBase):
    class ResponseElements(Model):
        queueUrl = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def _internal_process(self, event_name, session, location, agent):
        client = session.client('sqs')
        collector = SqsCollector(location, client, agent)
        collector.process_queue(self.responseElements.queueUrl)


class Sqs_UpdateQueue(CloudTrailEventBase):
    class RequestParameters(Model):
        queueUrl = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteQueue':
            agent.delete(self.requestParameters.queueUrl)
        elif event_name == 'PurgeQueue':
            # TODO this should probably emit some event to StackState
            pass
        else:
            client = session.client('sqs')
            collector = SqsCollector(location, client, agent)
            collector.process_queue(self.requestParameters.queueUrl)


class SqsCollector(RegisteredResourceCollector):
    API = "sqs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sqs"
    EVENT_SOURCE = "sqs.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        'CreateQueue': Sqs_CreateQueue,
        'DeleteQueue': Sqs_UpdateQueue,
        'AddPermission': True,
        'RemovePermission': True,
        'SetQueueAttributes': Sqs_UpdateQueue,
        'TagQueue': Sqs_UpdateQueue,
        'UntagQueue': Sqs_UpdateQueue,
        'PurgeQueue': Sqs_UpdateQueue
    }

    def process_all(self, filter=None):
        for queue_url in self.client.list_queues().get('QueueUrls', []):
            self.process_queue(queue_url)

    def process_queue(self, queue_url):
        queue_data_raw = self.client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        ).get('Attributes', {})
        queue_name = get_queue_name_from_url(queue_url)
        queue_data = make_valid_data(queue_data_raw)
        queue_arn = self.agent.create_arn('AWS::SQS::Queue', queue_name)
        queue_data['Tags'] = self.client.list_queue_tags(QueueUrl=queue_url).get('Tags')
        queue_data['URN'] = [queue_url]
        queue_data['Name'] = queue_url
        queue_data['QueueUrl'] = queue_url
        queue_data.update(with_dimensions([{'key': 'QueueName', 'value': queue_name}]))

        self.agent.component(queue_arn, self.COMPONENT_TYPE, queue_data)
