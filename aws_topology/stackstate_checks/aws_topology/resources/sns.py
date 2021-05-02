from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='sns', region=region, account_id=account_id, resource_id=resource_id)


class SnsCollector(RegisteredResourceCollector):
    API = "sns"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sns"

    def process_all(self, filter=None):
        sns = {}
        for topic_page in self.client.get_paginator('list_topics').paginate():
            for topic_data_raw in topic_page.get('Topics') or []:
                topic_data = make_valid_data(topic_data_raw)
                result = self.process_topic(topic_data)
                sns.update(result)
        return sns

    def process_topic(self, topic_data):
        topic_arn = topic_data['TopicArn']
        topic_data['Name'] = topic_arn
        topic_name = topic_arn.rsplit(':', 1)[-1]
        topic_data.update(with_dimensions([{'key': 'TopicName', 'value': topic_name}]))
        topic_data["Tags"] = self.client.list_tags_for_resource(ResourceArn=topic_arn).get('Tags') or []
        self.agent.component(topic_arn, self.COMPONENT_TYPE, topic_data)
        for subscriptions_by_topicpage in self.client.get_paginator('list_subscriptions_by_topic').paginate(
                TopicArn=topic_arn):
            for subscription_by_topic in subscriptions_by_topicpage.get('Subscriptions') or []:
                if subscription_by_topic['Protocol'] in ['lambda', 'sqs'] and \
                        subscription_by_topic['TopicArn'] == topic_arn:
                    # TODO subscriptions can be cross region! probably also cross account
                    self.agent.relation(topic_arn, subscription_by_topic['Endpoint'], 'uses service', {})
        return {topic_name: topic_arn}
