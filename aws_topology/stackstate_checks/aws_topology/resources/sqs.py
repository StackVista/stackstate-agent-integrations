from .utils import make_valid_data, with_dimensions
from .registry import RegisteredResourceCollector


class SQS_Collector(RegisteredResourceCollector):
    API = "sqs"
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
