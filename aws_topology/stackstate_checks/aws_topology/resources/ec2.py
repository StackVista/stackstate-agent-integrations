from collections import namedtuple
import time
from .utils import (
    client_array_operation,
    make_valid_data,
    create_host_urn,
    create_resource_arn,
    create_hash,
    set_required_access_v2,
    transformation,
)
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType, ModelType, ListType, BooleanType


InstanceData = namedtuple("InstanceData", ["instance", "instance_type"])


class Tag(Model):
    Key = StringType(required=True)
    Value = StringType(required=True)


class Subnet(Model):
    SubnetId = StringType(required=True)
    Tags = ListType(ModelType(Tag), default=[])
    AvailabilityZone = StringType(required=True)
    VpcId = StringType(required=True)


class Vpc(Model):
    VpcId = StringType(required=True)
    IsDefault = BooleanType(default=False)
    Tags = ListType(ModelType(Tag), default=[])


class SecurityGroup(Model):
    GroupName = StringType(default="UKNOWN")
    GroupId = StringType(required=True)
    VpcId = StringType()


class VpnGateway(Model):
    class VpnGatewayVpcAttachment(Model):
        VpcId = StringType(required=True)
        State = StringType(default="UNKNOWN")

    VpnGatewayId = StringType(required=True)
    VpcAttachments = ListType(ModelType(VpnGatewayVpcAttachment), default=[])


class InstanceType(Model):
    InstanceType = StringType(required=True)
    Hypervisor = StringType(default="")


class Instance(Model):
    class InstanceState(Model):
        Name = StringType(required=True)

    class SecurityGroup(Model):
        GroupId = StringType(required=True)

    InstanceId = StringType(required=True)
    InstanceType = StringType(required=True)
    State = ModelType(InstanceState)
    Tags = ListType(ModelType(Tag), default=[])
    PrivateIpAddress = StringType()
    PublicDnsName = StringType()
    PublicIpAddress = StringType()
    SubnetId = StringType()
    VpcId = StringType()
    SecurityGroups = ListType(ModelType(SecurityGroup), default=[])


class RunInstances(Model):
    class ResponseElements(Model):
        class InstancesSet(Model):
            class RunInstance(Model):
                instanceId = StringType(required=True)

            items = ListType(ModelType(RunInstance), required=True)

        instancesSet = ModelType(InstancesSet, required=True)

    responseElements = ModelType(ResponseElements, required=True)


class Ec2InstanceCollector(RegisteredResourceCollector):
    API = "ec2"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.ec2"

    def __init__(self, location_info, client, agent):
        RegisteredResourceCollector.__init__(self, location_info, client, agent)
        self.instance_types = {}

    def process_all(self, filter=None):
        if not filter or "instances" in filter:
            self.process_instances()
        if not filter or "security_groups" in filter:
            self.process_security_groups()
        if not filter or "vpcs" in filter:
            self.process_vpcs()
        if not filter or "subnets" in filter:
            self.process_subnets()
        if not filter or "vpn_gateways" in filter:
            self.process_vpn_gateways()

    @set_required_access_v2("ec2:DescribeInstanceTypes")
    def collect_instance_type(self, instance_type):
        # Items never change, only added, safe to hold in memory
        if instance_type not in self.instance_types:
            instance_type_data = self.client.describe_instance_types(InstanceTypes=[instance_type]).get(
                "InstanceTypes", []
            )
            if instance_type_data:
                self.instance_types[instance_type] = instance_type_data[0]
        return self.instance_types.get(instance_type, {})

    def collect_instance(self, instance_data):
        instance_type = instance_data.get("InstanceType", "")
        instance_type_data = self.collect_instance_type(instance_type) or {}
        return InstanceData(instance=instance_data, instance_type=instance_type_data)

    def collect_instances(self, **kwargs):
        for reservation in client_array_operation(
            self.client,
            "describe_instances",
            "Reservations",
            Filters=[
                {
                    "Name": "instance-state-code",  # Don't return terminated instances
                    "Values": [
                        "0",  # pending
                        "16",  # running
                        "32",  # shutting-down
                        "64",  # stopping
                        "80",  # stopped
                    ],
                }
            ],
            **kwargs
        ):
            for instance_data in reservation.get("Instances", []):
                yield self.collect_instance(instance_data)

    @set_required_access_v2("ec2:DescribeInstances")
    def process_instances(self, **kwargs):
        for data in self.collect_instances(**kwargs):
            self.process_instance(data)

    def process_some_instances(self, ids):
        self.process_instances(InstanceIds=ids)

    @transformation()
    def process_instance_type(self, data):
        instance_type = InstanceType(data, strict=False)
        instance_type.validate()
        return instance_type

    @transformation()
    def process_instance(self, data):
        instance = Instance(data.instance, strict=False)
        instance.validate()

        self.agent.event(
            {
                "timestamp": int(time.time()),
                "event_type": "ec2_state",
                "msg_title": "EC2 instance state",
                "msg_text": instance.State.Name,
                "host": instance.InstanceId,
                "tags": ["state:" + instance.State.Name],
            }
        )

        output = make_valid_data(data.instance)
        output["URN"] = [
            create_host_urn(instance.InstanceId),
            create_resource_arn(
                "ec2",
                self.location_info.Location.AwsRegion,
                self.location_info.Location.AwsAccount,
                "instance",
                instance.InstanceId,
            ),
        ]
        if not instance.Tags:
            output["Tags"] = []
        output["Tags"].append({"Key": "host", "Value": instance.InstanceId})
        output["Tags"].append({"Key": "instance-id", "Value": instance.InstanceId})
        if instance.PrivateIpAddress:
            output["Tags"].append({"Key": "private-ip", "Value": instance.PrivateIpAddress})
        if instance.PublicDnsName:
            output["URN"].append(create_host_urn(instance.PublicDnsName))
            output["Tags"].append({"Key": "fqdn", "Value": instance.PublicDnsName})
        if instance.PublicIpAddress:
            output["URN"].append(create_host_urn(instance.PublicIpAddress))
            output["Tags"].append({"Key": "public-ip", "Value": instance.PublicIpAddress})

        if data.instance_type:  # Don't run if instance type not found
            instance_type = self.process_instance_type(data.instance_type)
            output["isNitro"] = instance_type.Hypervisor == "nitro"

        # Map the subnet and if not available then map the VPC
        if instance.SubnetId:
            self.emit_relation(instance.InstanceId, instance.SubnetId, "uses service", {})
        elif instance.VpcId:  # pragma: no cover
            self.emit_relation(instance.InstanceId, instance.VpcId, "uses service", {})

        for security_group in instance.SecurityGroups:
            self.emit_relation(instance.InstanceId, security_group.GroupId, "uses service", {})

        self.emit_component(instance.InstanceId, ".".join([self.COMPONENT_TYPE, "instance"]), output)

    def collect_security_groups(self):
        for security_group in client_array_operation(self.client, "describe_security_groups", "SecurityGroups"):
            yield security_group

    @set_required_access_v2("ec2:DescribeSecurityGroups")
    def process_security_groups(self):
        for security_group_data in self.collect_security_groups():
            self.process_security_group(security_group_data)

    @transformation()
    def process_security_group(self, data):
        security_group = SecurityGroup(data, strict=False)
        security_group.validate()
        output = make_valid_data(data)
        output["Version"] = create_hash(output)
        output["Name"] = security_group.GroupName
        output["URN"] = [
            create_resource_arn(
                "ec2",
                self.location_info.Location.AwsRegion,
                self.location_info.Location.AwsAccount,
                "security-group",
                security_group.GroupId,
            )
        ]
        if security_group.VpcId:  # pragma: no cover
            self.emit_relation(security_group.VpcId, security_group.GroupId, "has resource", {})

        self.emit_component(security_group.GroupId, "aws.security-group", output)

    def collect_vpcs(self):
        for vpc in client_array_operation(self.client, "describe_vpcs", "Vpcs"):
            yield vpc

    @set_required_access_v2("ec2:DescribeVpcs")
    def process_vpcs(self):
        for vpc_data in self.collect_vpcs():
            self.process_vpc(vpc_data)

    @transformation()
    def process_vpc(self, data):
        vpc = Vpc(data, strict=False)
        vpc.validate()
        output = make_valid_data(data)
        # construct a name
        vpc_name = vpc.VpcId
        name_tag = [tag for tag in vpc.Tags if tag.Key == "Name"]
        if vpc.IsDefault:
            vpc_name = "default"
        elif len(name_tag) > 0:
            vpc_name = name_tag[0].Value
        output["Name"] = vpc_name
        # add a URN
        output["URN"] = [
            create_resource_arn(
                "ec2", self.location_info.Location.AwsRegion, self.location_info.Location.AwsAccount, "vpc", vpc.VpcId
            )
        ]
        self.emit_component(vpc.VpcId, "aws.vpc", output)

    def collect_subnets(self):
        for subnet in client_array_operation(self.client, "describe_subnets", "Subnets"):
            yield subnet

    @set_required_access_v2("ec2:DescribeSubnets")
    def process_subnets(self):
        for subnet_data in self.collect_subnets():
            self.process_subnet(subnet_data)

    @transformation()
    def process_subnet(self, data):
        subnet = Subnet(data, strict=False)
        subnet.validate()
        output = make_valid_data(data)
        # construct a name
        subnet_name = subnet.SubnetId
        name_tag = [tag for tag in subnet.Tags if tag.Key == "Name"]
        if len(name_tag) > 0:
            subnet_name = name_tag[0].Value
        if subnet.AvailabilityZone:  # pragma: no cover
            subnet_name = "{}-{}".format(subnet_name, subnet.AvailabilityZone)
        output["Name"] = subnet_name
        # add a URN
        output["URN"] = [
            create_resource_arn(
                "ec2",
                self.location_info.Location.AwsRegion,
                self.location_info.Location.AwsAccount,
                "subnet",
                subnet.SubnetId,
            )
        ]
        self.emit_component(subnet.SubnetId, "aws.subnet", output)
        self.emit_relation(subnet.SubnetId, subnet.VpcId, "uses service", {})

    def collect_vpn_gateways(self):
        for vpn_gateway in client_array_operation(
            self.client,
            "describe_vpn_gateways",
            "VpnGateways",
            Filters=[{"Name": "state", "Values": ["pending", "available"]}],
        ):
            yield vpn_gateway

    @set_required_access_v2("ec2:DescribeVpnGateways")
    def process_vpn_gateways(self):
        for vpn_gateway_data in self.collect_vpn_gateways():
            self.process_vpn_gateway(vpn_gateway_data)

    @transformation()
    def process_vpn_gateway(self, data):
        vpn_gateway = VpnGateway(data, strict=False)
        vpn_gateway.validate()
        output = make_valid_data(data)
        output["Name"] = vpn_gateway.VpnGatewayId
        self.emit_component(vpn_gateway.VpnGatewayId, "aws.vpngateway", output)
        for vpn_attachment in vpn_gateway.VpcAttachments:
            if vpn_attachment.State == "attached":
                self.emit_relation(vpn_gateway.VpnGatewayId, vpn_attachment.VpcId, "uses service", {})

    @transformation()
    def process_batch_instances(self, event, seen):
        data = RunInstances(event, strict=False)
        data.validate()
        instance_ids = [instance.instanceId for instance in data.responseElements.instancesSet.items]
        self.process_instances(InstanceIds=instance_ids)
        return instance_ids

    def process_state_notification(self, event, seen):
        instance_id = event.get("instance-id", "")
        if event.get("state") == "terminated":
            self.agent.delete(instance_id)
        else:
            self.process_instances(InstanceIds=[instance_id])

    def process_one_instance(self, instance_id):
        self.process_instances(InstanceIds=[instance_id])

    EVENT_SOURCE = "ec2.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "RunInstances", "processor": process_batch_instances},
        {"event_name": "StartInstances", "processor": process_batch_instances},
        {"event_name": "StopInstances", "processor": process_batch_instances},
        {"event_name": "TerminateInstances", "processor": process_batch_instances},
        {"event_name": "InstanceStateChangeNotification", "processor": process_state_notification},
        {"event_name": "AttachVolume", "path": "responseElements.instanceId", "processor": process_one_instance},
        {"event_name": "DetachVolume", "path": "responseElements.instanceId", "processor": process_one_instance},
        {
            "event_name": "ModifyInstanceAttribute",
            "path": "requestParameters.instanceId",
            "processor": process_one_instance,
        },
    ]
