from collections import namedtuple
from .utils import (
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from schematics import Model
from schematics.types import StringType, ModelType, DictType
from .registry import RegisteredResourceCollector


class Service(Model):
    Id = StringType(required=True)


class Instance(Model):
    Attributes = DictType(StringType())


class Namespace(Model):
    class NamespaceProperties(Model):
        class NamespaceDnsProperties(Model):
            HostedZoneId = StringType()

        DnsProperties = ModelType(NamespaceDnsProperties)

    Properties = ModelType(NamespaceProperties, required=True)


ServiceDiscoveryData = namedtuple("ServiceDiscoveryData", ["service", "instances", "namespace"])


class ServiceDiscoveryCollector(RegisteredResourceCollector):
    API = "servicediscovery"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.servicediscovery"

    @set_required_access_v2("servicediscovery:ListInstances")
    def collect_instances(self, service_id):
        return [
            instance
            for instance in client_array_operation(self.client, "list_instances", "Instances", ServiceId=service_id)
        ]

    @set_required_access_v2("servicediscovery:GetNamespace")
    def collect_namespace(self, namespace_id):
        return self.client.get_namespace(Id=namespace_id).get("Namespace", {})

    @set_required_access_v2("servicediscovery:GetService")
    def collect_service_description(self, service_id):
        # list_services does not return all fields, for example NamespaceId
        return self.client.get_service(Id=service_id).get("Service", {})

    def collect_service(self, service_data):
        service_id = service_data.get("Id")
        data = self.collect_service_description(service_id) or service_data
        instances = self.collect_instances(service_id) or []
        namespace = {}
        if data.get("DnsConfig", {}).get("NamespaceId"):
            namespace = self.collect_namespace(data["DnsConfig"]["NamespaceId"]) or {}
        return ServiceDiscoveryData(service=data, instances=instances, namespace=namespace)

    def collect_services(self):
        for service in [
            self.collect_service(service_data)
            for service_data in client_array_operation(self.client, "list_services", "Services")
        ]:
            yield service

    @set_required_access_v2("servicediscovery:ListServices")
    def process_services(self):
        for service_data in self.collect_services():
            self.process_service(service_data)

    def process_all(self, filter=None):
        if not filter or "services" in filter:
            self.process_services()

    @transformation()
    def process_instance(self, data, hosted_zone_id):
        instance = Instance(data, strict=False)
        instance.validate()

        if "ECS_SERVICE_NAME" in instance.Attributes:
            service_arn = "arn:aws:ecs:{}:{}:service/{}".format(
                self.location_info.Location.AwsRegion,
                self.location_info.Location.AwsAccount,
                instance.Attributes["ECS_SERVICE_NAME"],
            )
            self.emit_relation(service_arn, hosted_zone_id, "uses service", {})
        # Don't make a relation to EC2 if ECS is being used - this could be done directly in ECS
        elif "EC2_INSTANCE_ID" in instance.Attributes:
            self.emit_relation(instance.Attributes["EC2_INSTANCE_ID"], hosted_zone_id, "uses instance", {})

    @transformation()
    def process_service(self, data):
        # If no namespace data exists, do nothing
        if data.namespace:
            namespace = Namespace(data.namespace, strict=False)
            namespace.validate()

            if namespace.Properties.DnsProperties.HostedZoneId:
                for instance in data.instances:
                    self.process_instance(instance, namespace.Properties.DnsProperties.HostedZoneId)
