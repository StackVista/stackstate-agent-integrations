from .utils import make_valid_data, with_dimensions, create_arn as arn, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='sns', region=region, account_id=account_id, resource_id=resource_id)


class SNSEventBase(CloudTrailEventBase):
    def get_collector_class(self):
        return SnsCollector

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == 'D':
            agent.delete(self.get_resource_arn(agent, location))
        else:
            client = session.client('sns')
            collector = SnsCollector(location, client, agent)
            collector.process_one_topic(self.get_resource_arn(agent, location))


class SNSEventUpdate(SNSEventBase):
    class RequestParameters(Model):
        topicArn = StringType()

    requestParameters = ModelType(RequestParameters)

    def get_resource_name(self):
        part = self.requestParameters.topicArn.rsplit(':', 1)[-1]
        name = part.rsplit('/', 1)[-1]
        return name

    def get_operation_type(self):
        return 'U' if self.eventName != 'DeleteTopic' else 'D'


class SNSEventCreate(SNSEventBase):
    class ResponseElements(Model):
        topicArn = StringType()

    responseElements = ModelType(ResponseElements)

    def get_resource_name(self):
        part = self.responseElements.topicArn.rsplit(':', 1)[-1]
        name = part.rsplit('/', 1)[-1]
        return name

    def get_operation_type(self):
        return 'C'


class SnsCollector(RegisteredResourceCollector):
    API = "sns"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sns"
    EVENT_SOURCE = "sns.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        'CreateTopic': SNSEventCreate,
        'DeleteTopic': SNSEventUpdate,
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
                if subscription_by_topic['Protocol'] in ['lambda', 'sqs'] and \
                        subscription_by_topic['TopicArn'] == topic_arn:
                    # TODO subscriptions can be cross region! probably also cross account
                    self.agent.relation(topic_arn, subscription_by_topic['Endpoint'], 'uses service', {})
