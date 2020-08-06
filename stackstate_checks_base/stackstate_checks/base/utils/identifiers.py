
class Identifiers(object):
    """
    The util class that creates all StackState based identifiers prefix with urn.
    All identifiers should have the format urn:namespace:/some:identifying:values.
    Namespaces within an identifier are signalled with namespace:/ meaning that you can have identifiers in a format as:
        urn:namespace:/value:namespace2:/value2
    """
    urnPrefix = "urn"

    @staticmethod
    def create_host_identifier(host):
        """
        create a host identifier that can be used to merge with hosts in StackState
        args: `hostname`
        `hostname` can be the machine name or the fully qualified domain name (fqdn). In the case of AWS it can
        be the AWS instanceId.
        """
        return "urn:host:/{}".format(host)

    @staticmethod
    def create_process_identifier(host, pid, create_time):
        """
        create a process identifier that can be used to merge with processes in StackState
        args: `host, pid, create_time`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift, or the containerId if the processes is in any container environment.
        """
        return "urn:process:/{}:{}:{}".format(host, pid, create_time)

    @staticmethod
    def create_container_identifier(host, container_id):
        """
        create a container identifier that can be used to merge with containers in StackState
        args: `host, container_id`
        `host` can be the machine name or the fully qualified domain name (fqdn), as well as the pod name in the case
        of Kubernetes / OpenShift.
        """
        return "urn:container:/{}:{}".format(host, container_id)

    @staticmethod
    def create_trace_service_identifier(service_name):
        """
        create a trace service identifier that can be used to merge with trace services in StackState
        args: `service_name`
        """
        return "urn:service:/{}".format(service_name)

    @staticmethod
    def create_trace_service_instance_identifier(service_instance_identifier):
        """
        create a trace service instance identifier that can be used to merge with service instances in StackState
        args: `service_instance_identifier`
        `service_instance_identifier` is built up in the context of where the trace originated from, thus it's left to
        the implementer to decide the identifier structure.
        """
        return "urn:service-instance:/{}".format(service_instance_identifier)

    @staticmethod
    def create_integration_identifier(host, integration_type):
        return "urn:agent-integration:/{}:{}".format(host, integration_type)

    @staticmethod
    def create_integration_instance_identifier(host, integration_type, integration_url):
        return "urn:agent-integration-instance:/{}:{}:{}".format(host, integration_type,
                                                                integration_url)

    @staticmethod
    def create_agent_identifier(host):
        return "urn:stackstate-agent:/{}".format(host)

    @staticmethod
    def create_stackstate_identifier(identifier_namespace, identifier):
        return "urn:{}:/{}".format(identifier_namespace, identifier)
