from .utils import make_valid_data, with_dimensions, CloudTrailEventBase, create_arn as arn
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='sqs', region='', account_id=account_id, resource_id=resource_id)


def get_queue_name_from_url(url):
    return url.rsplit('/', 1)[-1]


class SqsEventBase(CloudTrailEventBase):
    def get_collector_class(self):
        return SqsCollector

    def _internal_process(self, session, location, agent):
        operation_type = self.get_operation_type()
        if operation_type == 'D':
            agent.delete(agent.create_arn(
                'AWS::SQS::Queue',
                location,
                get_queue_name_from_url(self.get_resource_name())
            ))
        elif operation_type == 'E':
            # TODO this should probably emit some event to StackState
            pass
        else:
            client = session.client('sqs')
            collector = SqsCollector(location, client, agent)
            collector.process_queue(self.get_resource_name())


class Sqs_CreateQueue(SqsEventBase):
    class ResponseElements(Model):
        queueUrl = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def get_resource_name(self):
        return self.responseElements.queueUrl

    def get_operation_type(self):
        return 'C'


class Sqs_UpdateQueue(SqsEventBase):
    class RequestParameters(Model):
        queueUrl = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)

    def get_resource_name(self):
        return self.requestParameters.queueUrl

    def get_operation_type(self):
        if self.eventName == 'DeleteQueue':
            return 'D'
        elif self.eventName == 'PurgeQueue':
            return 'E'
        return 'U'


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
    CLOUDFORMATION_TYPE = 'AWS::SQS::Queue'

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
        queue_arn = self.agent.create_arn('AWS::SQS::Queue', self.location_info, queue_name)
        queue_data['Tags'] = self.client.list_queue_tags(QueueUrl=queue_url).get('Tags')
        queue_data['URN'] = [queue_url]
        queue_data['Name'] = queue_url
        queue_data['QueueUrl'] = queue_url
        queue_data.update(with_dimensions([{'key': 'QueueName', 'value': queue_name}]))

        self.emit_component(queue_arn, self.COMPONENT_TYPE, queue_data)
