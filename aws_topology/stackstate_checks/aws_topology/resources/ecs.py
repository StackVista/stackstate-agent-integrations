import boto3
from botocore.config import Config
from .utils import make_valid_data, with_dimensions, create_arn as arn
from .registry import RegisteredResourceCollector


DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT
    )
)


def create_cluster_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='ecs', region=region, account_id=account_id, resource_id='cluster/' + resource_id)


class EcsCollector(RegisteredResourceCollector):
    API = "ecs"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.ecs.cluster"
    MEMORY_KEY = "ecs_cluster"

    def process_all(self, filter=None):
        ecs_cluster = {}
        for cluster_page in self.client.get_paginator('list_clusters').paginate():
            cluster_arns = cluster_page.get('clusterArns') or []
            for cluster_data_raw in self.client.describe_clusters(
                clusters=cluster_arns, include=['TAGS']
            ).get('clusters') or []:
                cluster_data = make_valid_data(cluster_data_raw)
                result = self.process_cluster(cluster_data)
                ecs_cluster.update(result)

            for cluster_arn in cluster_arns:
                for container_instance_page in self.client.get_paginator(
                    'list_container_instances'
                ).paginate(cluster=cluster_arn):
                    if len(container_instance_page['containerInstanceArns']) > 0:
                        described_container_instance = self.client.describe_container_instances(
                            cluster=cluster_arn,
                            containerInstances=container_instance_page['containerInstanceArns']
                        )
                        for container_instance in described_container_instance['containerInstances']:
                            self.agent.relation(cluster_arn, container_instance['ec2InstanceId'], 'uses_ec2_host', {})

        return ecs_cluster

    def process_cluster(self, cluster_data):
        cluster_arn = cluster_data['clusterArn']
        cluster_name = cluster_data['clusterName']
        cluster_data['Name'] = cluster_name
        cluster_data.update(with_dimensions([
            {'key': 'ClusterName', 'value': cluster_name}
        ]))
        self.agent.component(cluster_arn, self.COMPONENT_TYPE, cluster_data)

        # key: service_name, value: list of container_name
        self.ecs_containers_per_service = self.process_cluster_tasks(cluster_arn)

        self.process_services(cluster_arn, cluster_name)

        return {cluster_name: cluster_arn}

    def process_cluster_tasks(self, cluster_arn):
        task_map = {}
        for task_page in self.client.get_paginator('list_tasks').paginate(cluster=cluster_arn):
            if len(task_page['taskArns']) >= 1:
                for task_data_raw in self.client.describe_tasks(
                    cluster=cluster_arn,
                    tasks=task_page['taskArns']
                ).get('tasks') or []:
                    task_data = make_valid_data(task_data_raw)
                    result = self.process_cluster_task(cluster_arn, task_data)
                    task_map.update(result)
        return task_map

    def process_cluster_task(self, cluster_arn, task_data):
        task_definition_arn = task_data['taskDefinitionArn']
        task_data['Name'] = task_definition_arn[task_definition_arn.rfind('/') + 1:]

        # add a service instance identifier so it can merge with trace instance services
        identifiers = []
        container_names = []
        task_group = task_data['group']

        if task_group.startswith('service:'):
            has_group_service = True
            base_identifier = "urn:service-instance:/{0}".format(task_group.replace(':', "-"))
            for container in task_data['containers']:
                # this follow the same format that Traefik uses to name the backend
                # the trace agent uses the backend.meta tag present in the client span to create
                # the identifier for the service and service-instance components
                container_names.append('{0}-{1}'.format(task_group.replace(':', "-"), container['name']))
                if 'networkInterfaces' in container:
                    for interface in container['networkInterfaces']:
                        identifiers.append(
                            '{0}-{1}:/{2}'.format(base_identifier, container['name'], interface['privateIpv4Address'])
                        )
        else:
            has_group_service = False

        task_data['URN'] = identifiers
        task_arn = task_data['taskArn']
        # TODO self.logger.debug('task {2}, group {0}: {1}'.
        # format(task_group, ecs_containers_per_service[task_group], task_data['Name']))

        self.agent.component(task_arn, 'aws.ecs.task', task_data)
        if not has_group_service:
            self.agent.relation(cluster_arn, task_arn, 'has_cluster_node', {})
        return {
            task_group: {
                'taskArn': task_arn,
                'names': container_names
            }
        }

    def process_services(self, cluster_arn, cluster_name):
        for services_page in self.client.get_paginator('list_services').paginate(cluster=cluster_arn):
            if len(services_page['serviceArns']) >= 1:
                for service_data_raw in self.client.describe_services(
                        cluster=cluster_arn, include=['TAGS'], services=services_page['serviceArns'])['services']:
                    service_data = make_valid_data(service_data_raw)
                    self.process_service(cluster_arn, cluster_name, service_data)

    def process_service(self, cluster_arn, cluster_name, service_data):
        service_arn = service_data['serviceArn']
        service_name = service_data['serviceName']
        for lb in service_data['loadBalancers']:
            if "targetGroupArn" in lb:
                self.agent.relation(service_arn, lb['targetGroupArn'], 'uses service', {})
        service_data['Name'] = service_name
        service_data.update(with_dimensions([
            {'key': 'ClusterName', 'value': cluster_name},
            {'key': 'ServiceName', 'value': service_name}
        ]))

        # remove events because they do not belong to a component
        service_data.pop('events', None)

        # add a service identifier so it can merge with trace services
        prefixed_service_name = "service:" + service_name
        if prefixed_service_name in self.ecs_containers_per_service:
            containers = self.ecs_containers_per_service[prefixed_service_name]
            identifiers = []
            base_identifier = "urn:service:/"
            for container_name in containers['names']:
                identifiers.append(base_identifier + container_name)
            service_data['URN'] = identifiers

            # TODO self.logger.debug('ecs service {0} with identifiers: {1}'.format(service_name, identifiers))

            # create a relation with the task
            self.agent.relation(service_arn, containers['taskArn'], 'has_cluster_node', {})
        # else:
        # TODO   self.logger.warning('no containers for ecs service {0}'.format(service_name))

        self.agent.component(service_arn, 'aws.ecs.service', service_data)
        self.agent.relation(cluster_arn, service_arn, 'has_cluster_node', {})

        # TODO makes new client ? should we do that here ?
        for registry in service_data['serviceRegistries']:
            registry_arn = registry['registryArn']
            discovery_client = boto3.client('servicediscovery', config=DEFAULT_BOTO3_CONFIG)
            servicediscovery_list = discovery_client.list_services()['Services']

            filtered_registries = list(
                filter(lambda x: x['Arn'] in registry_arn, servicediscovery_list))

            if len(filtered_registries) == 1:
                service = discovery_client.get_service(Id=filtered_registries[0]['Id'])['Service']
                namespace_id = service['DnsConfig']['NamespaceId']
                namespace_data = discovery_client.get_namespace(Id=namespace_id)
                hosted_zone_id = namespace_data['Namespace']['Properties']['DnsProperties']['HostedZoneId']
                self.agent.relation(service_arn, '/hostedzone/' + hosted_zone_id, 'uses service', {})
