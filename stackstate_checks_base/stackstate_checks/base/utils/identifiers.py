
class Identifiers(object):
    """
    The util class that creates all StackState based identifiers prefix with urn.
    All identifiers should have the format urn:namespace:/some:identifying:values.
    Namespaces within an identifier are signalled with namespace:/ meaning that you can have identifiers in a format as:
        urn:namespace:/value:namespace2:/value2
    """

    @staticmethod
    def create_host_identifier(host):
        """
        creates a host identifier that can be used to merge with hosts in StackState.
        args: `hostname`
        `hostname` can be the machine name or the fully qualified domain name (fqdn). In the case of AWS it can
        be the AWS instanceId.
        """
        return "urn:host:/{}".format(host)

    @staticmethod
    def create_process_identifier(host, pid, create_time):
        """
        creates a process identifier that can be used to merge with processes in StackState.
        args: `host, pid, create_time`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift, or the containerId if the processes is in any container environment.
        """
        return "urn:process:/{}:{}:{}".format(host, pid, create_time)

    @staticmethod
    def create_container_identifier(host, container_id):
        """
        creates a container identifier that can be used to merge with containers in StackState.
        args: `host, container_id`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift.
        """
        return "urn:container:/{}:{}".format(host, container_id)

    @staticmethod
    def create_trace_service_identifier(service_name):
        """
        creates a trace service identifier that can be used to merge with trace services in StackState.
        args: `service_name`
        """
        return "urn:service:/{}".format(service_name)

    @staticmethod
    def create_trace_service_instance_identifier(service_instance_identifier):
        """
        creates a trace service instance identifier that can be used to merge with service instances in StackState.
        args: `service_instance_identifier`
        `service_instance_identifier` is built up in the context of where the trace originated from, thus it's left to
        the implementer to decide the identifier structure.
        """
        return "urn:service-instance:/{}".format(service_instance_identifier)

    @staticmethod
    def create_integration_identifier(host, integration_type):
        """
        creates a agent integration identifier that is used for the integrations running in the agent.
        args: `host`, `integration_type`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift.
        `integration_type` is the type of the integration eg. vsphere, zabbix, etc.
        """
        return "urn:agent-integration:/{}:{}".format(host, integration_type)

    @staticmethod
    def create_integration_instance_identifier(host, integration_type, integration_url):
        """
        creates a agent integration instance identifier that is used for the integration instances running in the agent.
        args: `host`, `integration_type`, `integration_url`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift.
        `integration_type` is the type of the integration eg. vsphere, zabbix, etc.
        `integration_url` is the url / name / identifier of the integration instance.
        """
        return "urn:agent-integration-instance:/{}:{}:{}".format(host, integration_type, integration_url)

    @staticmethod
    def create_agent_identifier(host):
        """
        creates a agent identifier that is used for the stackstate agent.
        args: `host`, `integration_type`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift.
        """
        return "urn:stackstate-agent:/{}".format(host)

    @staticmethod
    def create_custom_identifier(identifier_namespace, identifier):
        """
        creates a urn based identifier that can be used in StackState.
        args: `identifier_namespace`, `identifier`
        `identifier_namespace` is the namespace that this identifier falls in, typically this in the source or the
        component / relation type eg. kubernetes, stackstate-agent
        `identifier` is the actual identifying part of the identifier. This can also include sub-namespaces as described
        in the class definition.
        """
        return "urn:{}:/{}".format(identifier_namespace, identifier)

    @staticmethod
    def append_lowercase_identifiers(identifiers):
        """
        Appends the lowercase version of existing identifiers to identifiers list.
        It is done for the following namespaces: urn:host, urn:process, urn:container, urn:service, urn:service-instance

        :param identifiers: list of urn identifiers
        :return: list of identifiers with appended lowercase ones
        """
        urn_types = ['urn:host:', 'urn:process:', 'urn:container:', 'urn:service:', 'urn:service-instance:']
        lowercase_identifiers = []
        for identifier in [element for element in identifiers if element[:element.find('/')] in urn_types]:
            if identifier.lower() != identifier:
                lowercase_identifiers.append(identifier.lower())
        return identifiers + lowercase_identifiers
