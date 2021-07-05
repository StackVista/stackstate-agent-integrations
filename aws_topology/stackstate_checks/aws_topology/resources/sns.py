from .utils import (
    make_valid_data,
    with_dimensions,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="sns", region=region, account_id=account_id, resource_id=resource_id)


TopicData = namedtuple("TopicData", ["topic", "tags", "subscriptions"])


class Topic(Model):
    TopicArn = StringType(required=True)


class Subscription(Model):
    Endpoint = StringType()
    Protocol = StringType()
    TopicArn = StringType(required=True)


class SnsCollector(RegisteredResourceCollector):
    API = "sns"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sns"
    CLOUDFORMATION_TYPE = "AWS::SNS::Topic"

    @set_required_access_v2("sns:ListTagsForResource")
    def collect_tags(self, topic_arn):
        return self.client.list_tags_for_resource(ResourceArn=topic_arn).get("Tags", [])

    @set_required_access_v2("sns:GetTopicAttributes")
    def collect_topic_description(self, topic_arn):
        return self.client.get_topic_attributes(TopicArn=topic_arn).get("Attributes", {})

    def collect_subscriptions(self, topic_arn):
        for subscription in client_array_operation(
            self.client, "list_subscriptions_by_topic", "Subscriptions", TopicArn=topic_arn
        ):
            yield subscription

    @set_required_access_v2("sns:ListSubscriptionsByTopic")
    def process_subscriptions(self, topic_arn):
        return [subscription for subscription in self.collect_subscriptions(topic_arn)]

    def collect_topic(self, topic_data):
        topic_arn = topic_data.get("TopicArn")
        # If topic collection fails, just use the object returned by topic_data as this has the ARN
        data = self.collect_topic_description(topic_arn) or topic_data
        # If ARN collection fails, skip tag collection
        tags = self.collect_tags(topic_arn) or []
        subscriptions = self.process_subscriptions(topic_arn) or []
        return TopicData(topic=data, tags=tags, subscriptions=subscriptions)

    def collect_topics(self):
        for topic_data in client_array_operation(self.client, "list_topics", "Topics"):
            yield self.collect_topic(topic_data)

    def process_all(self, filter=None):
        if not filter or "topics" in filter:
            self.process_topics()

    @set_required_access_v2("sns:ListTopics")
    def process_topics(self):
        for topic_data in self.collect_topics():
            self.process_topic(topic_data)

    def process_one_topic(self, topic_arn):
        self.process_topic(self.collect_topic({"TopicArn": topic_arn}))

    @transformation()
    def process_topic(self, data):
        topic = Topic(data.topic, strict=False)
        topic.validate()
        output = make_valid_data(data.topic)
        topic_arn = topic.TopicArn
        topic_name = topic_arn.rsplit(":", 1)[-1]
        output["Name"] = topic_name
        output["Tags"] = data.tags
        output.update(with_dimensions([{"key": "TopicName", "value": topic_name}]))
        self.emit_component(topic_arn, ".".join([self.COMPONENT_TYPE, "topic"]), output)

        for subscription_by_topic in data.subscriptions:
            subscription = Subscription(subscription_by_topic, strict=False)
            subscription.validate()
            if subscription.Protocol in ["lambda", "sqs"]:
                # TODO subscriptions can be cross region! probably also cross account
                self.emit_relation(topic_arn, subscription.Endpoint, "uses service", {})

    EVENT_SOURCE = "sns.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateTopic", "path": "responseElements.topicArn", "processor": process_one_topic},
        {
            "event_name": "DeleteTopic",
            "path": "requestParameters.topicArn",
            "processor": RegisteredResourceCollector.emit_deletion,
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
