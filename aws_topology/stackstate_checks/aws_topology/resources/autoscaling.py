from .utils import make_valid_data, set_required_access_v2, client_array_operation, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ListType, ModelType


class AutoScalingEventBase(CloudTrailEventBase):
    def get_collector_class(self):
        return AutoscalingCollector


class AutoScalingEvent(AutoScalingEventBase):
    class RequestParameters(Model):
        autoScalingGroupName = StringType()

    requestParameters = ModelType(RequestParameters)

    def get_operation_type(self):
        return 'D' if self.eventName == 'DeleteAutoScalingGroup' else 'U'

    def get_resource_name(self):
        return self.requestParameters.autoScalingGroupName

    def _internal_process(self, session, location, agent):
        if self.get_operation_type() == 'D':
            agent.delete(self.get_resource_name())
        else:
            client = session.client('autoscaling')
            collector = AutoscalingCollector(location, client, agent)
            collector.process_one_auto_scaling_group(self.get_resource_name())


class AutoScalingTagEvent(AutoScalingEventBase):
    class RequestParameters(Model):
        class AutoScalingTag(Model):
            resourceType = StringType(required=True)
            resourceId = StringType(required=True)
        tags = ListType(ModelType(AutoScalingTag), required=True)

    requestParameters = ModelType(RequestParameters)

    def get_operation_type(self):
        return 'U'

    def get_resource_name(self):
        if len(self.requestParameters.tags) > 0:
            tag = self.requestParameters.tags[0]
            return tag.resourceId
        return ""

    def _internal_process(self, session, location, agent):
        name = self.get_resource_name()
        # TODO refactoring needed multiple resource type possible here
        if name:
            if self.requestParameters.tags[0].resourceType == 'auto-scaling-group':
                client = session.client('autoscaling')
                collector = AutoscalingCollector(location, client, agent)
                collector.process_one_auto_scaling_group(name)


class AutoScalingGroup(Model):
    class Instance(Model):
        InstanceId = StringType(required=True)

    AutoScalingGroupARN = StringType(required=True)
    AutoScalingGroupName = StringType(required=True)
    Instances = ListType(ModelType(Instance), default=[])
    LoadBalancerNames = ListType(StringType, default=[])
    TargetGroupARNs = ListType(StringType, default=[])
    ServiceLinkedRoleARN = StringType()


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
    CLOUDFORMATION_TYPE = "AWS::AutoScaling::AutoScalingGroup"

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
        self.emit_component(auto_scaling_group.AutoScalingGroupName, self.COMPONENT_TYPE, output)

        if auto_scaling_group.ServiceLinkedRoleARN:
            self.agent.relation(
                auto_scaling_group.AutoScalingGroupARN,
                auto_scaling_group.ServiceLinkedRoleARN,
                'uses service',
                {}
            )

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
