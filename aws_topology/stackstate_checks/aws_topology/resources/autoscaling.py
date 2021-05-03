from .utils import make_valid_data, set_required_access_v2, client_array_operation, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ListType, ModelType


class AutoScalingEvent(CloudTrailEventBase):
    class RequestParameters(Model):
        autoScalingGroupName = StringType()

    requestParameters = ModelType(RequestParameters)

    def _internal_process(self, event_name, session, location, agent):
        if event_name == 'DeleteAutoScalingGroup':
            agent.delete(self.requestParameters.autoScalingGroupName)
        else:
            client = session.client('autoscaling')
            collector = AutoscalingCollector(location, client, agent)
            collector.process_one_auto_scaling_group(self.requestParameters.autoScalingGroupName)


class AutoScalingTagEvent(CloudTrailEventBase):
    class RequestParameters(Model):
        class AutoScalingTag(Model):
            resourceType = StringType(required=True)
            resourceId = StringType(required=True)
        tags = ListType(ModelType(AutoScalingTag), required=True)

    requestParameters = ModelType(RequestParameters)

    def _internal_process(self, event_name, session, location, agent):
        if len(self.requestParameters.tags) > 0:
            tag = self.requestParameters.tags[0]
            if tag.resourceType == 'auto-scaling-group':
                client = session.client('autoscaling')
                collector = AutoscalingCollector(location, client, agent)
                collector.process_one_auto_scaling_group(tag.resourceId)


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
    EVENT_SOURCE = "autoscaling.amazonaws.com"
    CLOUDTRAIL_EVENTS = {
        "CreateAutoScalingGroup": AutoScalingEvent,
        "DeleteAutoScalingGroup": AutoScalingEvent,
        "UpdateAutoScalingGroup": AutoScalingEvent,
        "CreateOrUpdateTags": AutoScalingTagEvent
    }

    def collect_auto_scaling_groups(self, **kwargs):
        for auto_scaling_group in client_array_operation(
            self.client,
            'describe_auto_scaling_groups',
            'AutoScalingGroups',
            **kwargs
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

    def process_autoscaling_group(self, data):
        output = make_valid_data(data)
        auto_scaling_group = AutoScalingGroup(data, strict=False)
        auto_scaling_group.validate()
        output['URN'] = [
            auto_scaling_group.AutoScalingGroupARN
        ]
        # using name here, s unique in region, arn is not resolvable from CF-resources
        self.agent.component(auto_scaling_group.AutoScalingGroupName, self.COMPONENT_TYPE, output)

        for instance in auto_scaling_group.Instances:
            self.agent.relation(auto_scaling_group.AutoScalingGroupARN, instance.InstanceId, 'uses service', {})

        for load_balancer_name in auto_scaling_group.LoadBalancerNames:
            self.agent.relation(
                'classic_elb_' + load_balancer_name,
                auto_scaling_group.AutoScalingGroupARN,
                'uses service',
                {}
            )

            for instance in auto_scaling_group.Instances:
                # removing elb instances if there are any
                relation_id = 'classic_elb_' + load_balancer_name + '-uses service-' + instance.InstanceId
                self.agent.delete(relation_id)

        for target_group_arn in auto_scaling_group.TargetGroupARNs:
            self.agent.relation(target_group_arn, auto_scaling_group.AutoScalingGroupARN, 'uses service', {})

            for instance in auto_scaling_group.Instances:
                # removing elb instances if there are any
                relation_id = target_group_arn + '-uses service-' + instance.InstanceId
                self.agent.delete(relation_id)
