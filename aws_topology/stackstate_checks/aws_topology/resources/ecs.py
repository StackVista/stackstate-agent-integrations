from collections import namedtuple
from .utils import (
    make_valid_data,
    with_dimensions,
    create_arn as arn,
    client_array_operation,
    set_required_access_v2,
    transformation,
)
from schematics import Model
from schematics.types import StringType, ListType, ModelType
from .registry import RegisteredResourceCollector


def create_cluster_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource="ecs", region=region, account_id=account_id, resource_id="cluster/" + resource_id)


class TaskMapItem(Model):
    taskArn = StringType()
    names = ListType(StringType())


class Task(Model):
    class TaskContainers(Model):
        class TaskContainerNetworkInterface(Model):
            privateIpv4Address = StringType()

        name = StringType(default="UNKNOWN")
        networkInterfaces = ListType(ModelType(TaskContainerNetworkInterface), default=[])

    taskArn = StringType(required=True)
    taskDefinitionArn = StringType()
    group = StringType(default="UNKNOWN")
    containers = ListType(ModelType(TaskContainers), default=[])


class Service(Model):
    class ServiceLoadBalancers(Model):
        targetGroupArn = StringType()

    serviceArn = StringType(required=True)
    serviceName = StringType()
    clusterArn = StringType(required=True)
    loadBalancers = ListType(ModelType(ServiceLoadBalancers), default=[])


class ContainerInstance(Model):
    ec2InstanceId = StringType(required=True)


class Cluster(Model):
    clusterArn = StringType(required=True)
    clusterName = StringType()


ClusterData = namedtuple("ClusterData", ["cluster", "container_instances", "tasks", "services"])


class EcsCollector(RegisteredResourceCollector):
    API = "ecs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.ecs"
    MAX_PAGE_SIZE = 100  # Number of items that can be fetched in one describe_* page call

    @set_required_access_v2("")
    def collect_service_page(self, cluster_arn, service_arns):
        max_calls = self.MAX_PAGE_SIZE
        return self.client.describe_services(
            cluster=cluster_arn, include=["TAGS"], services=service_arns[:max_calls]
        ).get("services", [])

    @set_required_access_v2("ecs:ListServices")
    def collect_services(self, cluster_arn):
        services = []
        service_arns = []
        for service_arn in client_array_operation(self.client, "list_services", "serviceArns", cluster=cluster_arn):
            if len(service_arns) >= self.MAX_PAGE_SIZE:
                # If no service pages are returned, instead return a minimal object with the data we have
                services += self.collect_service_page(cluster_arn, service_arns) or [
                    {"serviceArn": sarn, "clusterArn": cluster_arn} for sarn in service_arns
                ]
                service_arns = []
            else:
                service_arns.append(service_arn)
        # Process any leftover items, if they exist
        if service_arns:
            services += self.collect_service_page(cluster_arn, service_arns) or [
                {"serviceArn": sarn, "clusterArn": cluster_arn} for sarn in service_arns
            ]
        return services

    @set_required_access_v2("ecs:DescibeTasks")
    def collect_task_page(self, cluster_arn, task_arns):
        max_calls = self.MAX_PAGE_SIZE
        return self.client.describe_tasks(cluster=cluster_arn, tasks=task_arns[:max_calls]).get("tasks", [])

    @set_required_access_v2("ecs:ListTasks")
    def collect_tasks(self, cluster_arn):
        tasks = []
        task_arns = []
        for task_arn in client_array_operation(self.client, "list_tasks", "taskArns", cluster=cluster_arn):
            if len(task_arns) >= self.MAX_PAGE_SIZE:
                # If no task pages are returned, instead return a minimal object with the data we have
                tasks += self.collect_task_page(cluster_arn, task_arns) or [
                    {"taskArn": tarn, "clusterArn": cluster_arn} for tarn in task_arns
                ]
                task_arns = []
            else:
                task_arns.append(task_arn)
        # Process any leftover items, if they exist
        if task_arns:
            tasks += self.collect_task_page(cluster_arn, task_arns) or [
                {"taskArn": tarn, "clusterArn": cluster_arn} for tarn in task_arns
            ]
        return tasks

    @set_required_access_v2("ecs:DescribeContainerInstances")
    def collect_container_instance_page(self, cluster_arn, container_instance_arns):
        max_calls = self.MAX_PAGE_SIZE
        return self.client.describe_container_instances(
            cluster=cluster_arn, containerInstances=container_instance_arns[:max_calls]
        ).get("containerInstances", [])

    @set_required_access_v2("ecs:ListContainerInstances")
    def collect_container_instances(self, cluster_arn):
        container_instances = []
        container_instance_arns = []
        for container_instance_arn in client_array_operation(
            self.client, "list_container_instances", "containerInstanceArns", cluster=cluster_arn
        ):
            if len(container_instance_arns) >= self.MAX_PAGE_SIZE:
                # Don't attempt to create a minimal object here as we require data from describe_container_instances
                container_instances += self.collect_container_instance_page(cluster_arn, container_instance_arns) or []
                container_instance_arns = []
            else:
                container_instance_arns.append(container_instance_arn)
        if container_instance_arns:
            container_instances += self.collect_container_instance_page(cluster_arn, container_instance_arns) or []
        return container_instances

    @set_required_access_v2("ecs:DescribeClusters")
    def collect_cluster_page(self, cluster_arns):
        return self.client.describe_clusters(clusters=cluster_arns, include=["TAGS"]).get("clusters", [])

    def collect_clusters(self):
        for cluster_arn in client_array_operation(self.client, "list_clusters", "clusterArns"):
            yield cluster_arn

    def process_cluster_page(self, cluster_arns):
        for data in self.collect_cluster_page(cluster_arns) or [
            {"clusterArn": cluster_arn} for cluster_arn in cluster_arns
        ]:
            cluster_arn = data.get("clusterArn")
            container_instances = self.collect_container_instances(cluster_arn) or []
            tasks = self.collect_tasks(cluster_arn) or []
            services = self.collect_services(cluster_arn) or []
            self.process_cluster(
                ClusterData(cluster=data, container_instances=container_instances, tasks=tasks, services=services)
            )

    @set_required_access_v2("ecs:ListClusters")
    def process_clusters(self):
        cluster_arns = []
        for cluster_arn in self.collect_clusters():
            if len(cluster_arns) >= self.MAX_PAGE_SIZE:
                self.process_cluster_page(cluster_arns)
                cluster_arns = []
            else:
                cluster_arns.append(cluster_arn)
        if cluster_arns:
            self.process_cluster_page(cluster_arns)

    def process_all(self, filter=None):
        if not filter or "clusters" in filter:
            self.process_clusters()

    def process_task(self, cluster, data):
        task = Task(data, strict=False)
        task.validate()
        output = make_valid_data(data)
        # If no task definition ARN is found, use the UUID of the task as the name
        output["Name"] = (task.taskDefinitionArn or task.taskArn).rsplit("/", 1)[1]

        # add a service instance identifier so it can merge with trace instance services
        identifiers = []
        container_names = []

        if task.group.startswith("service:"):
            base_identifier = "urn:service-instance:/{0}".format(task.group.replace(":", "-"))
            for container in task.containers:
                # this follow the same format that Traefik uses to name the backend
                # the trace agent uses the backend.meta tag present in the client span to create
                # the identifier for the service and service-instance components
                container_names.append("{0}-{1}".format(task.group.replace(":", "-"), container["name"]))
                for interface in container.networkInterfaces:
                    identifiers.append(
                        "{0}-{1}:/{2}".format(base_identifier, container.name, interface.privateIpv4Address)
                    )
        else:
            # Only emit a direct relation between a task and a cluster if the task has no service
            self.emit_relation(cluster.clusterArn, task.taskArn, "has_cluster_node", {})

        output["URN"] = identifiers
        self.emit_component(task.taskArn, ".".join([self.COMPONENT_TYPE, "task"]), output)
        return {task.group: TaskMapItem({"taskArn": task.taskArn, "names": container_names})}

    @transformation()
    def process_service(self, cluster, data, task_map):
        service = Service(data, strict=False)
        service.validate()
        output = make_valid_data(data)
        service_arn = service.serviceArn
        service_name = service.serviceName or service_arn.rsplit("/", 1)[1]
        output["Name"] = service_name
        output.update(
            with_dimensions(
                [{"key": "ClusterName", "value": cluster.clusterName}, {"key": "ServiceName", "value": service_name}]
            )
        )

        for lb in service.loadBalancers:
            if lb.targetGroupArn:
                self.emit_relation(service_arn, lb.targetGroupArn, "uses service", {})

        # remove events because they do not belong to a component
        output.pop("events", None)

        # add a service identifier so it can merge with trace services
        prefixed_service_name = "service:" + service_name
        if prefixed_service_name in task_map:
            containers = task_map[prefixed_service_name]
            identifiers = []
            base_identifier = "urn:service:/"
            for container_name in containers.names:
                identifiers.append(base_identifier + container_name)
            output["URN"] = identifiers
            # create a relation with the task
            self.emit_relation(service_arn, containers.taskArn, "has_cluster_node", {})

        self.emit_component(service_arn, "aws.ecs.service", output)
        self.emit_relation(cluster.clusterArn, service_arn, "has_cluster_node", {})

    @transformation()
    def process_container_instance(self, cluster, data):
        container_instance = ContainerInstance(data, strict=False)
        container_instance.validate()
        self.emit_relation(cluster.clusterArn, container_instance.ec2InstanceId, "uses_ec2_host", {})

    @transformation()
    def process_cluster(self, data):
        cluster = Cluster(data.cluster, strict=False)
        cluster.validate()
        output = make_valid_data(data.cluster)
        cluster_arn = cluster.clusterArn
        # If ecs:DescribeClusters is not granted, we can infer name from ARN
        cluster_name = cluster.clusterName or cluster_arn.rsplit("/", 1)[1]
        output["Name"] = cluster_name
        output.update(with_dimensions([{"key": "ClusterName", "value": cluster_name}]))
        self.emit_component(cluster_arn, ".".join([self.COMPONENT_TYPE, "cluster"]), output)

        for container_instance in data.container_instances:
            self.process_container_instance(cluster, container_instance)

        task_map = {}
        for task in data.tasks:
            task_map.update(self.process_task(cluster, task))

        for service in data.services:
            self.process_service(cluster, service, task_map)

    def process_one_cluster(self, cluster_arn):
        self.process_cluster_page([cluster_arn])

    EVENT_SOURCE = "ecs.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {
            "event_name": "CreateCluster",
            "path": "responseElements.cluster.clusterArn",
            "processor": process_one_cluster,
        },
        {
            "event_name": "CreateService",
            "path": "responseElements.service.clusterArn",
            "processor": process_one_cluster,
        },
    ]
