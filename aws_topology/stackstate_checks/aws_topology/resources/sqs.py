from .utils import make_valid_data, with_dimensions, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


class SqsCollector(RegisteredResourceCollector):
    API = "sqs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sqs"

    def process_all(self):
        sqs = {}
        for queue_url in self.client.list_queues().get('QueueUrls', []):
            result = self.process_queue(queue_url)
            sqs.update(result)
        return sqs

    def process_queue(self, queue_url):
        queue_data_raw = self.client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        ).get('Attributes', {})
        queue_data = make_valid_data(queue_data_raw)
        queue_arn = queue_data.get('QueueArn')
        queue_data['Tags'] = self.client.list_queue_tags(QueueUrl=queue_url).get('Tags')
        queue_data['URN'] = [queue_url]
        queue_data['Name'] = queue_url
        queue_data['QueueUrl'] = queue_url
        queue_name = queue_url.rsplit('/', 1)[-1]
        queue_data.update(with_dimensions([{'key': 'QueueName', 'value': queue_name}]))

        self.agent.component(queue_arn, self.COMPONENT_TYPE, queue_data)

        return {queue_name: queue_arn}


class Sqs_CreateQueue(CloudTrailEventBase):
    class ResponseElements(Model):
        queueUrl = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def process(self, event_name, session, location, agent):
        client = session.client('sqs')
        collector = SqsCollector(location, client, agent)
        collector.process_queue(self.responseElements.queueUrl)


class Sqs_UpdateQueue(CloudTrailEventBase):
    class RequestParameters(Model):
        queueUrl = StringType(required=True)

    requestParameters = ModelType(RequestParameters, required=True)

    def process(self, event_name, session, location, agent):
        if event_name == 'DeleteQueue':
            agent.delete(self.requestParameters.queueUrl)
        elif event_name == 'PurgeQueue':
            # TODO this should probably emit some event to StackState
            pass
        else:
            client = session.client('sqs')
            collector = SqsCollector(location, client, agent)
            collector.process_queue(self.requestParameters.queueUrl)
