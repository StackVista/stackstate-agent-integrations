from .utils import (
    make_valid_data,
    with_dimensions,
    extract_dimension_name,
    update_dimensions,
    create_security_group_relations,
)
import time
from .registry import RegisteredResourceCollector
from collections import namedtuple


LoadBalancerData = namedtuple("LoadBalancerData", ["description", "tags", "listeners"])


class ElbV2Collector(RegisteredResourceCollector):
    API = "elbv2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.elb_v2"

    def process_all(self, filter=None):
        # can't filter because of data dependency
        lb_types = self.process_load_balancers()
        self.process_target_groups(lb_types)

    def process_load_balancers(self):
        lb_type = {}
        for elb_data_raw in self.client.describe_load_balancers().get("LoadBalancers") or []:
            result = self.process_load_balancer(elb_data_raw)
            lb_type.update(result)
        return lb_type

    def process_one_load_balancer(self, arn):
        for elb_data_raw in self.client.describe_load_balancers(LoadBalancerArns=[arn]).get("LoadBalancers") or []:
            self.process_load_balancer(elb_data_raw)

    def process_target_groups(self, lb_types):
        for target_group_data_raw in self.client.describe_target_groups().get("TargetGroups") or []:
            self.process_target_group(target_group_data_raw, lb_types)

    def process_one_target_group(self, arn):
        for target_group_data_raw in self.client.describe_target_groups(TargetGroupArns=arn).get("TargetGroups") or []:
            self.process_target_group(target_group_data_raw)

    def process_load_balancer(self, data):
        elb_data = make_valid_data(data)
        elb_external_id = elb_data["LoadBalancerArn"]
        # can become 1 call!
        elb_tags = self.client.describe_tags(ResourceArns=[elb_external_id]).get("TagDescriptions")
        if isinstance(elb_tags, list) and len(elb_tags) > 0:
            elb_tags = elb_tags[0].get("Tags") or []
        elb_type = "aws.elb_v2_" + elb_data["Type"].lower()
        elb_data["Tags"] = elb_tags
        elb_data["Name"] = elb_data["LoadBalancerName"]
        elb_data["listeners"] = []

        elb_data.update(
            with_dimensions([{"Key": "LoadBalancer", "Value": extract_dimension_name(elb_external_id, "loadbalancer")}])
        )
        vpc_id = elb_data["VpcId"]

        create_security_group_relations(elb_external_id, elb_data, self.agent)

        # data of all listeners is added to the component
        for listener_raw in (
            self.client.describe_listeners(LoadBalancerArn=elb_data["LoadBalancerArn"]).get("Listeners") or []
        ):
            listener = make_valid_data(listener_raw)
            elb_data["listeners"].append(listener)

        self.emit_component(elb_external_id, elb_type, elb_data)
        self.emit_relation(elb_external_id, vpc_id, "uses service", {})
        return {elb_external_id: elb_data["Type"].lower()}

    def process_target_group(self, data, lb_types={}):
        target_group_data = make_valid_data(data)
        target_group_external_id = target_group_data["TargetGroupArn"]
        vpc_id = target_group_data["VpcId"]
        target_group_data["Name"] = target_group_data["TargetGroupName"]
        target_group_data.update(
            with_dimensions(
                [
                    {
                        "Key": "TargetGroup",
                        "Value": "targetgroup/" + extract_dimension_name(target_group_external_id, "targetgroup"),
                    }
                ]
            )
        )
        # TODO strange the 1st loadbalancer that targets this group is used to specify TargetLoadBalancerType+dim
        # there is no test for this...
        if len(target_group_data["LoadBalancerArns"]) > 0:
            loadbalancer_arn = target_group_data["LoadBalancerArns"][0]
            elb_target_type = lb_types.get(loadbalancer_arn)
            if elb_target_type:
                target_group_data["TargetLoadBalancerType"] = elb_target_type
            update_dimensions(
                target_group_data,
                {"Key": "LoadBalancer", "Value": extract_dimension_name(loadbalancer_arn, "loadbalancer")},
            )

        self.emit_component(target_group_external_id, "aws.elb_v2_target_group", target_group_data)

        self.emit_relation(target_group_external_id, vpc_id, "uses service", {})

        for elb_arn in target_group_data["LoadBalancerArns"]:
            elb_target_group_data = {}
            elb_target_group_data.update(self.location_info.to_primitive())
            self.emit_relation(elb_arn, target_group_external_id, "uses service", elb_target_group_data)

        # emit health events for all TargetGroups
        for target_raw in (
            self.client.describe_target_health(TargetGroupArn=target_group_data["TargetGroupArn"]).get(
                "TargetHealthDescriptions"
            )
            or []
        ):
            target = make_valid_data(target_raw)
            # assuming instance here, IP is another option
            target_external_id = target["Target"]["Id"]

            target_data = target
            target_data["Name"] = target_external_id
            target_data["URN"] = [
                # This id will match the EC2 instance
                target_external_id
            ]

            # Adding urn:aws/ to make it unique from the EC2 instance id
            self.emit_component(
                "urn:aws/target-group-instance/" + target_external_id, "aws.elb_v2_target_group_instance", target_data
            )

            # relation between target group and target
            self.emit_relation(
                target_group_external_id, "urn:aws/target-group-instance/" + target_external_id, "uses service", {}
            )

            event = {
                "timestamp": int(time.time()),
                "event_type": "target_instance_health",
                "msg_title": "Target instance health",
                "msg_text": target_data["TargetHealth"]["State"],
                "host": target_data["Target"]["Id"],
                "tags": [
                    "state:" + target_data["TargetHealth"]["State"],
                    "reason:" + str(target_data["TargetHealth"].get("Reason")),
                ],
            }

            self.agent.event(event)

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
