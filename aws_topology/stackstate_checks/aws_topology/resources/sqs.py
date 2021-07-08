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
import re


def create_arn(region=None, resource_id=None, **kwargs):
    if re.match(r"^https:\/\/sqs.[a-z]{2}-([a-z]*-){1,2}\d\.amazonaws\.com\/\d{12}\/.+$", resource_id):
        return arn(
            resource="sqs",
            region=resource_id.split(".", 2)[1],
            account_id=resource_id.rsplit("/", 2)[-2],
            resource_id=resource_id.rsplit("/", 1)[-1],
        )
    elif re.match(r"^https:\/\/queue\.amazonaws\.com\/\d{12}\/.+$", resource_id):
        return arn(
            resource="sqs",
            region=region,
            account_id=resource_id.rsplit("/", 2)[1],
            resource_id=resource_id.rsplit("/", 1)[-1],
        )
    elif re.match(r"^https:\/\/[a-z]{2}-([a-z]*-){1,2}\d\.queue\.amazonaws\.com\/\d{12}\/.+$", resource_id):
        return arn(
            resource="sqs",
            region=resource_id.split("/", 3)[2].split(".", 1)[0],
            account_id=resource_id.rsplit("/", 2)[1],
            resource_id=resource_id.rsplit("/", 1)[-1],
        )
    else:
        raise ValueError("SQS URL {} does not match expected regular expression".format(resource_id))


QueueData = namedtuple("QueueData", ["queue_url", "queue", "tags"])


class Queue(Model):
    QueueArn = StringType(required=True)


class SqsCollector(RegisteredResourceCollector):
    API = "sqs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.sqs"
    CLOUDFORMATION_TYPE = "AWS::SQS::Queue"

    @set_required_access_v2("sqs:ListQueueTags")
    def collect_tags(self, queue_url):
        return self.client.list_queue_tags(QueueUrl=queue_url).get("Tags", [])

    @set_required_access_v2("sqs:GetQueueAttributes")
    def collect_queue_description(self, queue_url):
        return self.client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"]).get("Attributes", {})

    def construct_queue_description(self, queue_url):
        return {"QueueArn": self.agent.create_arn("AWS::SQS::Queue", self.location_info, resource_id=queue_url)}

    def collect_queue(self, queue_url):
        data = self.collect_queue_description(queue_url) or self.construct_queue_description(queue_url)
        tags = self.collect_tags(queue_url) or []
        return QueueData(queue_url=queue_url, queue=data, tags=tags)

    def collect_queues(self):
        for queue_url in client_array_operation(self.client, "list_queues", "QueueUrls"):
            yield self.collect_queue(queue_url)

    def process_all(self, filter=None):
        if not filter or "queues" in filter:
            self.process_queues()

    @set_required_access_v2("sqs:ListQueues")
    def process_queues(self):
        for queue_data in self.collect_queues():
            self.process_queue(queue_data)

    def process_one_queue(self, queue_url):
        self.process_queue(self.collect_queue(queue_url))

    @transformation()
    def process_queue(self, data):
        queue = Queue(data.queue, strict=False)
        queue.validate()
        output = make_valid_data(data.queue)
        queue_arn = queue.QueueArn
        queue_name = queue_arn.rsplit(":", 1)[-1]
        output["Name"] = queue_name
        output["Tags"] = data.tags
        output["URN"] = [data.queue_url]
        output["QueueUrl"] = data.queue_url
        output.update(with_dimensions([{"key": "QueueName", "value": queue_name}]))
        self.emit_component(queue_arn, "queue", output)

    EVENT_SOURCE = "sqs.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateQueue", "path": "responseElements.queueUrl", "processor": process_one_queue},
        {
            "event_name": "DeleteQueue",
            "path": "requestParameters.queueUrl",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
        {
            "event_name": "AddPermission",
        },
        {
            "event_name": "RemovePermission",
        },
        {"event_name": "SetQueueAttributes", "path": "requestParameters.queueUrl", "processor": process_one_queue},
        {"event_name": "TagQueue", "path": "requestParameters.queueUrl", "processor": process_one_queue},
        {"event_name": "UntagQueue", "path": "requestParameters.queueUrl", "processor": process_one_queue},
        {"event_name": "PurgeQueue"},
    ]
