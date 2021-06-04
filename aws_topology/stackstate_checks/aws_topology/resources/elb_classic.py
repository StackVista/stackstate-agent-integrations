import time
from .utils import (
    make_valid_data,
    create_arn as arn,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ListType, ModelType


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(
        resource="elasticloadbalancing", region=region, account_id=account_id, resource_id="loadbalancer/" + resource_id
    )


LoadBalancerData = namedtuple("LoadBalancerData", ["elb", "tags", "instance_health"])


class LoadBalancerInstances(Model):
    InstanceId = StringType()


class LoadBalancer(Model):
    LoadBalancerName = StringType(required=True)
    VPCId = StringType()
    Instances = ListType(ModelType(LoadBalancerInstances))


class InstanceHealth(Model):
    InstanceId = StringType(required=True)
    State = StringType()
    Description = StringType()


class ELBClassicCollector(RegisteredResourceCollector):
    API = "elb"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.elb_classic"
    CLOUDFORMATION_TYPE = "AWS::ElasticLoadBalancing::LoadBalancer"

    @set_required_access_v2("elasticloadbalancing:DescribeTags")
    def collect_tag_page(self, elb_names):
        if len(elb_names) <= 20:
            return self.client.describe_tags(LoadBalancerNames=elb_names).get("TagDescriptions", [])
        else:
            return []

    @set_required_access_v2("elasticloadbalancing:DescribeLoadBalancers")
    def collect_elb_page(self, **kwargs):
        # This doesn't use the utils.client_array_operation function as we need control over grabbing one page at a time
        for elb_page in self.client.get_paginator("describe_load_balancers").paginate(
            PaginationConfig={
                "MaxItems": 20,  # Use 20 to match the describe_tags API call, where max items in one call is also 20
            },
            **kwargs
        ):
            yield elb_page.get("LoadBalancerDescriptions", [])

    @set_required_access_v2("elasticloadbalancing:DescribeInstanceHealth")
    def collect_instance_health(self, elb_name):
        return self.client.describe_instance_health(LoadBalancerName=elb_name).get("InstanceStates", [])

    def process_elbs(self, elb_names=[]):
        if elb_names:  # Only pass in LoadBalancerNames if a specific name is needed, otherwise ask for all
            paginator = self.collect_elb_page(LoadBalancerNames=elb_names)
        else:
            paginator = self.collect_elb_page()
        for elb_page in paginator or []:
            # The paginator fetches max 20 items, which is the max items that can be fetched with describe_tags
            tag_page = self.collect_tag_page([elb.get("LoadBalancerName", "") for elb in elb_page])
            for data in elb_page:
                instance_health = self.collect_instance_health(data.get("LoadBalancerName"))
                tags = []
                # Match the result from the fetched tags with the specific ELB
                for tag_result in tag_page:
                    if tag_result.get("LoadBalancerName") == data.get("LoadBalancerName"):
                        tags = tag_result.get("Tags", [])
                self.process_elb(LoadBalancerData(elb=data, tags=tags, instance_health=instance_health))

    def process_all(self, filter=None):
        if not filter or "loadbalancers" in filter:
            self.process_elbs()

    def process_one_elb(self, elb_name):
        self.process_elbs([elb_name])

    @transformation()
    def process_elb(self, data):
        elb = LoadBalancer(data.elb, strict=False)
        elb.validate()
        output = make_valid_data(data.elb)
        elb_name = elb.LoadBalancerName
        elb_arn = self.agent.create_arn(
            "AWS::ElasticLoadBalancing::LoadBalancer", self.location_info, resource_id=elb_name
        )
        output["Name"] = elb_name
        output["Tags"] = data.tags
        output["URN"] = [elb_arn]
        self.emit_component(elb_arn, self.COMPONENT_TYPE, output)

        vpc_id = elb.VPCId
        self.emit_relation(elb_arn, vpc_id, "uses service", {})

        for instance in output.get("Instances", []):
            instance_external_id = instance.get("InstanceId")  # ec2 instance
            self.emit_relation(elb_arn, instance_external_id, "uses service", {})

        for instance_health in data.instance_health:
            health = InstanceHealth(instance_health, strict=False)
            health.validate()
            self.agent.event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "ec2_state",
                    "msg_title": "EC2 instance state",
                    "msg_text": health.State,
                    "host": health.InstanceId,
                    "tags": ["state:" + health.State, "description:" + health.Description],
                }
            )

        self.agent.create_security_group_relations(elb_arn, output)

    EVENT_SOURCE = "elasticloadbalancing.amazonaws.com"
    API_VERSION = "2012-06-01"
    CLOUDTRAIL_EVENTS = [
        {
            "event_name": "CreateLoadBalancer",
            "path": "requestParameters.loadBalancerName",
            "processor": process_one_elb,
        },
        {
            "event_name": "DeleteLoadBalancer",
            "path": "requestParameters.loadBalancerName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
        {
            "event_name": "RegisterInstancesWithLoadBalancer",
            "path": "requestParameters.loadBalancerName",
            "processor": process_one_elb,
        },
    ]
