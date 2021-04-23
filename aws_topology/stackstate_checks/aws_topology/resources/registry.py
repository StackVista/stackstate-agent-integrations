from six import with_metaclass
from .utils import correct_tags, capitalize_keys


class ResourceRegistry(type):

    REGISTRY = {
        'global': {},
        'regional': {}
    }

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        """
            Here the name of the class is used as key but it could be any class
            parameter.
        """
        if '??' not in [new_cls.API, new_cls.API_TYPE]:
            if cls.REGISTRY[new_cls.API_TYPE].get(new_cls.API) is None:
                cls.REGISTRY[new_cls.API_TYPE][new_cls.API] = {}
            cls.REGISTRY[new_cls.API_TYPE][new_cls.API][new_cls.COMPONENT_TYPE] = new_cls
        return new_cls

    @classmethod
    def get_registry(cls):
        return dict(cls.REGISTRY)


class AgentProxy(object):
    def __init__(self, agent, location_info):
        self.agent = agent
        self.location_info = location_info
        self.delete_ids = []

    def component(self, id, type, data):
        data.update(self.location_info)
        self.agent.component(id, type, correct_tags(capitalize_keys(data)))

    def relation(self, source_id, target_id, type, data):
        self.agent.relation(source_id, target_id, type, data)

    def event(self, event):
        self.agent.event(event)

    def delete(self, id):
        self.delete_ids.append(id)

    def create_security_group_relations(self, resource_id, resource_data, security_group_field='SecurityGroups'):
        if resource_data.get(security_group_field):
            for security_group_id in resource_data[security_group_field]:
                self.relation(resource_id, security_group_id, 'uses service', {})


class RegisteredResourceCollector(with_metaclass(ResourceRegistry, object)):
    """
    Any class that will inherits from BaseRegisteredClass will be included
    inside the dict RegistryHolder.REGISTRY, the key being the name of the
    class and the associated value, the class itself.
    """
    API = "??"
    API_TYPE = "??"
    MEMORY_KEY = None
    COMPONENT_TYPE = "??"

    def __init__(self, location_info, client, agent):
        self.client = client
        self.location_info = location_info
        self.agent = AgentProxy(agent, location_info)

    def get_delete_ids(self):
        return self.agent.delete_ids
