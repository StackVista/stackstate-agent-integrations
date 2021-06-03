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


TopicData = namedtuple("TopicData", ["topic", "tags"])


class Topic(Model):
    TopicArn = StringType()


class Subscription(Model):
    Endpoint = StringType()
    Protocol = StringType()
    TopicArn = StringType()


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

    def collect_topic(self, topic_data):
        topic_arn = topic_data.get("TopicArn")
        # If topic collection fails, just use the object returned by topic_data as this has the ARN
        data = self.collect_topic_description(topic_arn) or topic_data
        # If ARN collection fails, skip tag collection
        if topic_arn:
            tags = self.collect_tags(topic_arn)
        else:
            tags = []
        return TopicData(topic=data, tags=tags)

    @set_required_access_v2("sns:ListTopics")
    def collect_topics(self):
        for topic in [
            self.collect_topic(topic_data)
            for topic_data in client_array_operation(self.client, "list_topics", "Topics")
        ]:
            yield topic

    def collect_subscriptions(self, topic_arn):
        for subscription in client_array_operation(
            self.client, "list_subscriptions_by_topic", "Subscriptions", TopicArn=topic_arn
        ):
            yield subscription

    def process_all(self, filter=None):
        if not filter or "aws.sns" in filter:
            for topic_data in self.collect_topics():
                try:
                    self.process_topic(topic_data)
                except Exception:
                    pass

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
        self.emit_component(topic_arn, self.COMPONENT_TYPE, output)

        for subscription_by_topic in self.collect_subscriptions(topic_arn):
            try:
                subscription = Subscription(subscription_by_topic, strict=False)
                subscription.validate()
                if subscription.Protocol in ["lambda", "sqs"] and subscription.TopicArn == topic_arn:
                    # TODO subscriptions can be cross region! probably also cross account
                    self.emit_relation(topic_arn, subscription.Endpoint, "uses service", {})
            except Exception:
                pass

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
