from .utils import make_valid_data, with_dimensions
from .registry import RegisteredResourceCollector


class SnsCollector(RegisteredResourceCollector):
    API = "sns"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sns"
    EVENT_SOURCE = "sns.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        'CreateTopic': True,
        'DeleteTopic': True
        # SetSMSAttributes
        # SetSubscriptionAttributes
        # SetTopicAttributes
        # Subscribe

        # CreatePlatformEndpoint
        # DeleteEndpoint
        # CreatePlatformApplication
        # DeletePlatformApplication
        # SetEndpointAttributes
        # SetPlatformApplicationAttributes
    }

    def process_all(self, filter=None):
        for topic_page in self.client.get_paginator('list_topics').paginate():
            for topic_data_raw in topic_page.get('Topics') or []:
                topic_data = make_valid_data(topic_data_raw)
                self.process_topic(topic_data)

    def process_topic(self, topic_data):
        topic_arn = topic_data['TopicArn']
        topic_data['Name'] = topic_arn
        topic_name = topic_arn.rsplit(':', 1)[-1]
        topic_data.update(with_dimensions([{'key': 'TopicName', 'value': topic_name}]))
        topic_data["Tags"] = self.client.list_tags_for_resource(ResourceArn=topic_arn).get('Tags') or []
        self.emit_component(topic_arn, self.COMPONENT_TYPE, topic_data)
        for subscriptions_by_topicpage in self.client.get_paginator('list_subscriptions_by_topic').paginate(
                TopicArn=topic_arn):
            for subscription_by_topic in subscriptions_by_topicpage.get('Subscriptions') or []:
                if subscription_by_topic['Protocol'] in ['lambda', 'sqs'] and \
                        subscription_by_topic['TopicArn'] == topic_arn:
                    # TODO subscriptions can be cross region! probably also cross account
                    # TODO get the subscription attributes to find SubscriptionRoleArn
                    self.agent.relation(topic_arn, subscription_by_topic['Endpoint'], 'uses service', {})
