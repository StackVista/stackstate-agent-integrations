from six import with_metaclass
from .cloudtrail import listen_for


class ResourceRegistry(type):

    REGISTRY = {
        'global': {},
        'regional': {}
    }
    CLOUDTRAIL = listen_for

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        """
            Here the name of the class is used as key but it could be any class
            parameter.
        """
        if '??' not in [new_cls.API, new_cls.API_TYPE]:
            cls.REGISTRY[new_cls.API_TYPE][new_cls.API] = new_cls
        if '??' != new_cls.EVENT_SOURCE and new_cls.CLOUDTRAIL_EVENTS is not None:
            cls.CLOUDTRAIL.update({
                new_cls.EVENT_SOURCE: new_cls.CLOUDTRAIL_EVENTS
            })
        return new_cls

    @classmethod
    def get_registry(cls):
        return dict(cls.REGISTRY)


class RegisteredResourceCollector(with_metaclass(ResourceRegistry, object)):
    """
    Any class that will inherits from BaseRegisteredClass will be included
    inside the dict RegistryHolder.REGISTRY, the key being the name of the
    class and the associated value, the class itself.
    """
    API = "??"
    API_TYPE = "??"
    COMPONENT_TYPE = "??"
    EVENT_SOURCE = "??"
    CLOUDTRAIL_EVENTS = None

    def __init__(self, location_info, client, agent):
        self.client = client
        self.agent = agent
        self.location_info = location_info

    def get_delete_ids(self):
        return self.agent.delete_ids

    def process_all(self, filter=None):
        raise NotImplementedError
