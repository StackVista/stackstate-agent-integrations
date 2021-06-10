from .utils import make_valid_data, set_required_access_v2, client_array_operation, transformation
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ListType, ModelType


class AutoScalingTagEvent(Model):
    class RequestParameters(Model):
        class AutoScalingTag(Model):
            resourceType = StringType(required=True)
            resourceId = StringType(required=True)

        tags = ListType(ModelType(AutoScalingTag), default=[])

    requestParameters = ModelType(RequestParameters)


class AutoScalingGroup(Model):
    class Instance(Model):
        InstanceId = StringType(required=True)

    AutoScalingGroupARN = StringType(required=True)
    AutoScalingGroupName = StringType(required=True)
    Instances = ListType(ModelType(Instance), default=[])
    LoadBalancerNames = ListType(StringType, default=[])
    TargetGroupARNs = ListType(StringType, default=[])


class AutoscalingCollector(RegisteredResourceCollector):
    API = "autoscaling"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.autoscaling"
    CLOUDFORMATION_TYPE = "AWS::AutoScaling::AutoScalingGroup"

    def collect_auto_scaling_groups(self, **kwargs):
        for auto_scaling_group in client_array_operation(
            self.client, "describe_auto_scaling_groups", "AutoScalingGroups", **kwargs
        ):
            yield auto_scaling_group

    @set_required_access_v2("autoscaling:DescribeAutoScalingGroups")
    def process_autoscaling_groups(self):
        for auto_scaling_group in self.collect_auto_scaling_groups():
            self.process_autoscaling_group(auto_scaling_group)

    @set_required_access_v2("autoscaling:DescribeAutoScalingGroups")
    def process_one_auto_scaling_group(self, group_name):
        for auto_scaling_group in self.collect_auto_scaling_groups(AutoScalingGroupNames=[group_name]):
            self.process_autoscaling_group(auto_scaling_group)

    def process_all(self, filter=None):
        self.process_autoscaling_groups()

    @transformation()
    def process_tag_event(self, event, seen):
        ids = []
        tagevent = AutoScalingTagEvent(event, strict=False)
        for tag in tagevent.requestParameters.tags:
            if tag.resourceType == "auto-scaling-group":
                if tag.resourceId not in seen:
                    self.process_one_auto_scaling_group(tag.resourceId)
                    ids.append(tag.resourceId)
        return ids

    def process_autoscaling_group(self, data):
        output = make_valid_data(data)
        auto_scaling_group = AutoScalingGroup(data, strict=False)
        auto_scaling_group.validate()
        output["URN"] = [auto_scaling_group.AutoScalingGroupARN]
        # using name here, s unique in region, arn is not resolvable from CF-resources
        self.emit_component(auto_scaling_group.AutoScalingGroupName, self.COMPONENT_TYPE, output)

        for instance in auto_scaling_group.Instances:
            self.emit_relation(auto_scaling_group.AutoScalingGroupARN, instance.InstanceId, "uses service", {})

        for load_balancer_name in auto_scaling_group.LoadBalancerNames:
            elb_arn = self.agent.create_arn(
                "AWS::ElasticLoadBalancing::LoadBalancer", self.location_info, resource_id=load_balancer_name
            )
            self.emit_relation(elb_arn, auto_scaling_group.AutoScalingGroupARN, "uses service", {})

            for instance in auto_scaling_group.Instances:
                # removing elb instances if there are any
                relation_id = elb_arn + "-uses service-" + instance.InstanceId
                self.agent.delete(relation_id)

        for target_group_arn in auto_scaling_group.TargetGroupARNs:
            self.emit_relation(target_group_arn, auto_scaling_group.AutoScalingGroupARN, "uses service", {})

            for instance in auto_scaling_group.Instances:
                # removing elb instances if there are any
                relation_id = target_group_arn + "-uses service-" + instance.InstanceId
                self.agent.delete(relation_id)

    EVENT_SOURCE = "autoscaling.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            "event_name": "CreateAutoScalingGroup",
            "path": "requestParameters.autoScalingGroupName",
            "processor": process_one_auto_scaling_group,
        },
        {
            "event_name": "DeleteAutoScalingGroup",
            "path": "requestParameters.autoScalingGroupName",
            "processor": RegisteredResourceCollector.process_delete_by_name,
        },
        {
            "event_name": "UpdateAutoScalingGroup",
            "path": "requestParameters.autoScalingGroupName",
            "processor": process_one_auto_scaling_group,
        },
        {"event_name": "CreateOrUpdateTags", "processor": process_tag_event},
    ]
