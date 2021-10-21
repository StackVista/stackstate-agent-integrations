from .utils import (
    client_array_operation,
    make_valid_data,
    set_required_access_v2,
    transformation,
    with_dimensions,
    extract_dimension_name,
    update_dimensions,
    create_security_group_relations,
)
import time
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ListType, ModelType


LoadBalancerData = namedtuple("LoadBalancerData", ["load_balancer", "tags", "listeners"])
TargetGroupData = namedtuple("TargetGroupData", ["target_group", "tags", "target_health", "load_balancers"])


class LoadBalancer(Model):
    LoadBalancerArn = StringType(required=True)
    LoadBalancerName = StringType(default="UNKNOWN")
    Type = StringType(required=True)
    VpcId = StringType(required=True)


class TargetGroup(Model):
    TargetGroupArn = StringType(required=True)
    TargetGroupName = StringType(default="UNKNOWN")
    VpcId = StringType()
    LoadBalancerArns = ListType(StringType(), default=[])


class TargetHealth(Model):
    class TargetHealthTarget(Model):
        Id = StringType(required=True)

    class TargetHealthTargetHealth(Model):
        State = StringType(required=True)
        Reason = StringType(default="None")

    Target = ModelType(TargetHealthTarget, required=True)
    TargetHealth = ModelType(TargetHealthTargetHealth, required=True)


class ElbV2Collector(RegisteredResourceCollector):
    API = "elbv2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.elb-v2"
    MAX_TAG_CALLS = 20

    def process_all(self, filter=None):
        load_balancers = []
        if not filter or "loadbalancers" in filter:
            load_balancers = self.process_load_balancers()
        if not filter or "targetgroups" in filter:
            self.process_target_groups(load_balancers)

    @set_required_access_v2("elasticloadbalancing:DescribeTags")
    def collect_tag_page(self, load_balancer_ids):
        max_items = self.MAX_TAG_CALLS
        return self.client.describe_tags(ResourceArns=load_balancer_ids[:max_items]).get("TagDescriptions", [])

    @set_required_access_v2("elasticloadbalancing:DescribeListeners")
    def collect_listeners(self, load_balancer_arn):
        return [
            listener
            for listener in client_array_operation(
                self.client, "describe_listeners", "Listeners", LoadBalancerArn=load_balancer_arn
            )
        ]

    def collect_load_balancers(self, **kwargs):
        return [
            load_balancer_data
            for load_balancer_data in client_array_operation(
                self.client, "describe_load_balancers", "LoadBalancers", **kwargs
            )
        ]

    def process_load_balancer_page(self, load_balancers):
        tag_page = (
            self.collect_tag_page([load_balancer.get("LoadBalancerArn") for load_balancer in load_balancers]) or []
        )
        for data in load_balancers:
            load_balancer_arn = data.get("LoadBalancerArn")
            listeners = self.collect_listeners(load_balancer_arn) or []
            tags = []
            for tag_result in tag_page:
                if tag_result.get("ResourceArn") == data.get("LoadBalancerArn"):
                    tags = tag_result.get("Tags", [])
            self.process_load_balancer(LoadBalancerData(load_balancer=data, tags=tags, listeners=listeners))

    @set_required_access_v2("elasticloadbalancing:DescribeLoadBalancers")
    def process_load_balancers(self, load_balancer_arns=[]):
        if load_balancer_arns:  # Only pass in LoadBalancerNames if a specific name is needed, otherwise ask for all
            load_balancers = self.collect_load_balancers(LoadBalancerArns=load_balancer_arns)
        else:
            load_balancers = self.collect_load_balancers()
        to_process = []
        for load_balancer in load_balancers or []:
            # Batch up load_balancers into groups, then process them in pages of 20
            if len(to_process) == self.MAX_TAG_CALLS:
                self.process_load_balancer_page(to_process)
                to_process = []
            else:
                to_process.append(load_balancer)
        # If we run out of load_balancers to process, process the last ones
        if to_process:
            self.process_load_balancer_page(to_process)
        return load_balancers

    @transformation()
    def process_load_balancer(self, data):
        load_balancer = LoadBalancer(data.load_balancer, strict=False)
        load_balancer.validate()
        output = make_valid_data(data.load_balancer)
        output["Name"] = load_balancer.LoadBalancerName
        output["Tags"] = data.tags
        output["listeners"] = [make_valid_data(listener) for listener in data.listeners]
        output.update(
            with_dimensions(
                [
                    {
                        "Key": "LoadBalancer",
                        "Value": extract_dimension_name(load_balancer.LoadBalancerArn, "loadbalancer"),
                    }
                ]
            )
        )

        create_security_group_relations(load_balancer.LoadBalancerArn, output, self.agent)
        load_balancer_type = load_balancer.Type.lower() + "-load-balancer"
        self.emit_component(load_balancer.LoadBalancerArn, load_balancer_type, output)
        self.emit_relation(load_balancer.LoadBalancerArn, load_balancer.VpcId, "uses-service", {})
        return {load_balancer.LoadBalancerArn: load_balancer.Type.lower()}

    def process_one_load_balancer(self, arn):
        self.process_load_balancers([arn])

    def collect_target_groups(self, **kwargs):
        for target_group in client_array_operation(self.client, "describe_target_groups", "TargetGroups", **kwargs):
            yield target_group

    @set_required_access_v2("elasticloadbalancing:DescribeTargetHealth")
    def collect_target_health(self, target_group_arn):
        return self.client.describe_target_health(TargetGroupArn=target_group_arn).get("TargetHealthDescriptions", [])

    def process_target_group_page(self, target_groups, load_balancers):
        tag_page = self.collect_tag_page([target_group.get("TargetGroupArn") for target_group in target_groups]) or []
        for data in target_groups:
            target_health = self.collect_target_health(data.get("TargetGroupArn")) or []
            tags = []
            # When using process_one, fetch necessary load balancers
            if not load_balancers and data.get("LoadBalancerArns"):
                load_balancers = self.process_load_balancers(data.get("LoadBalancerArns")) or []
            # Match the result from the fetched tags with the specific target group
            for tag_result in tag_page:
                if tag_result.get("ResourceArn") == data.get("TargetGroupArn"):
                    tags = tag_result.get("Tags", [])
            self.process_target_group(
                TargetGroupData(
                    target_group=data, tags=tags, target_health=target_health, load_balancers=load_balancers
                )
            )

    @set_required_access_v2("elasticloadbalancing:DescribeTargetGroups")
    def process_target_groups(self, load_balancers=[], target_group_names=[]):
        if target_group_names:
            paginator = self.collect_target_groups(TargetGroupArns=target_group_names)
        else:
            paginator = self.collect_target_groups()
        target_groups = []
        for target_group in paginator:
            # Batch up target_groups into groups, then process them in pages of 20
            if len(target_groups) == self.MAX_TAG_CALLS:
                self.process_target_group_page(target_groups, load_balancers)
                target_groups = []
            else:
                target_groups.append(target_group)
        # If we run out of target_groups to process, process the last ones
        if len(target_groups):
            self.process_target_group_page(target_groups, load_balancers)

    def process_one_target_group(self, arn):
        self.process_target_groups(target_group_names=[arn])

    @transformation()
    def process_target_health(self, data, target_group):
        target_health = TargetHealth(data, strict=False)
        target_health.validate()
        output = make_valid_data(data)
        # assuming instance here, IP is another option

        output["Name"] = target_health.Target.Id
        output["URN"] = [
            # This id will match the EC2 instance
            target_health.Target.Id
        ]

        # Adding urn:aws/ to make it unique from the EC2 instance id
        self.emit_component(
            "urn:aws/target-group-instance/" + target_health.Target.Id, "target-group-instance", output
        )

        # relation between target group and target
        self.emit_relation(
            target_group.TargetGroupArn, "urn:aws/target-group-instance/" + target_health.Target.Id, "uses-service", {}
        )

        self.agent.event(
            {
                "timestamp": int(time.time()),
                "event_type": "target_instance_health",
                "msg_title": "Target instance health",
                "msg_text": target_health.TargetHealth.State,
                "host": target_health.Target.Id,
                "tags": [
                    "state:" + target_health.TargetHealth.State,
                    "reason:" + target_health.TargetHealth.Reason,
                ],
            }
        )

    @transformation()
    def process_target_group(self, data):
        target_group = TargetGroup(data.target_group, strict=False)
        target_group.validate()
        output = make_valid_data(data.target_group)
        output["Name"] = target_group.TargetGroupName
        output["Tags"] = data.tags
        output.update(
            with_dimensions(
                [
                    {
                        "Key": "TargetGroup",
                        "Value": "targetgroup/" + extract_dimension_name(target_group.TargetGroupArn, "targetgroup"),
                    }
                ]
            )
        )

        if target_group.LoadBalancerArns:
            for load_balancer_data in data.load_balancers:
                load_balancer = LoadBalancer(load_balancer_data, strict=False)
                load_balancer.validate()
                # A target group can only have one load balancer at a time
                if load_balancer.LoadBalancerArn == target_group.LoadBalancerArns[0]:
                    output["TargetLoadBalancerType"] = load_balancer.Type.lower()
                    update_dimensions(
                        output,
                        {
                            "Key": "LoadBalancer",
                            "Value": extract_dimension_name(load_balancer.LoadBalancerArn, "loadbalancer"),
                        },
                    )

        self.emit_component(target_group.TargetGroupArn, "target-group", output)
        self.emit_relation(target_group.TargetGroupArn, target_group.VpcId, "uses-service", {})

        for load_balancer_arn in target_group.LoadBalancerArns:
            self.emit_relation(
                load_balancer_arn, target_group.TargetGroupArn, "uses-service", self.location_info.to_primitive()
            )

        # emit health events for all TargetGroups
        for target_health in data.target_health:
            self.process_target_health(target_health, target_group)

    EVENT_SOURCE = "elasticloadbalancing.amazonaws.com"
    API_VERSION = "2015-12-01"
    CLOUDTRAIL_EVENTS = [
        {
            "event_name": "CreateLoadBalancer",
            "path": "responseElements.loadBalancers.0.loadBalancerArn",
            "processor": process_one_load_balancer,
        },
        {
            "event_name": "DeleteLoadBalancer",
            "path": "requestParameters.loadBalancerArn",
            "processor": RegisteredResourceCollector.emit_deletion,
        },
        {
            "event_name": "CreateListener",
            "path": "responseElements.listeners.0.loadBalancerArn",
            "processor": process_one_load_balancer,
        },
        {
            "event_name": "CreateTargetGroup",
            "path": "responseElements.targetGroups.0.targetGroupArn",
            "processor": process_one_target_group,
        },
        {
            "event_name": "DeleteTargetGroup",
            "path": "requestParameters.targetGroupArn",
            "processor": RegisteredResourceCollector.emit_deletion,
        },
    ]
