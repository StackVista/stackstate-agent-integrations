from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='sns', region=region, account_id=account_id, resource_id=resource_id)


class SnsCollector(RegisteredResourceCollector):
    API = "sns"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sns"
    CLOUDFORMATION_TYPE = 'AWS::SNS::Topic'

    def process_all(self, filter=None):
        for topic_page in self.client.get_paginator('list_topics').paginate():
            for topic_data_raw in topic_page.get('Topics') or []:
                topic_data = make_valid_data(topic_data_raw)
                self.process_topic(topic_data)

    def process_one_topic(self, arn):
        self.process_topic({"TopicArn":  arn})

    def process_topic(self, topic_data):
        topic_arn = topic_data['TopicArn']
        topic_name = topic_arn.rsplit(':', 1)[-1]
        topic_data['Name'] = topic_name
        topic_data.update(with_dimensions([{'key': 'TopicName', 'value': topic_name}]))
        topic_data["Tags"] = self.client.list_tags_for_resource(ResourceArn=topic_arn).get('Tags') or []
        self.emit_component(topic_arn, self.COMPONENT_TYPE, topic_data)
        for subscriptions_by_topicpage in self.client.get_paginator('list_subscriptions_by_topic').paginate(
                TopicArn=topic_arn):
            for subscription_by_topic in subscriptions_by_topicpage.get('Subscriptions') or []:
                if subscription_by_topic['Protocol'] in ['lambda', 'sqs']:
                    # TODO subscriptions can be cross region! probably also cross account
                    self.agent.relation(topic_arn, subscription_by_topic['Endpoint'], 'uses service', {})

    EVENT_SOURCE = "sns.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            'event_name': 'CreateTopic',
            'path': 'responseElements.topicArn',
            'processor': process_one_topic
        },
        {
            'event_name': 'DeleteTopic',
            'path': 'requestParameters.topicArn',
            'processor': RegisteredResourceCollector.emit_deletion
        }
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
    ]
