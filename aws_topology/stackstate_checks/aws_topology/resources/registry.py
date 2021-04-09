from six import with_metaclass


class ResourceRegistry(type):

    REGISTRY = {}

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        """
            Here the name of the class is used as key but it could be any class
            parameter.
        """
        if new_cls.API != '??':
            if (cls.REGISTRY.get(new_cls.API) is None):
                cls.REGISTRY[new_cls.API] = []
            cls.REGISTRY[new_cls.API].append({
                'constructor': new_cls
            })
        return new_cls

    @classmethod
    def get_registry(cls):
        return dict(cls.REGISTRY)

    @classmethod
    def clear_registry(cls):
        cls.REGISTRY = {}


class RegisteredResource(with_metaclass(ResourceRegistry, object)):
    """
    Any class that will inherits from BaseRegisteredClass will be included
    inside the dict RegistryHolder.REGISTRY, the key being the name of the
    class and the associated value, the class itself.
    """
    API = "??"
    MEMORY_KEY = "??"

    def __init__(self, location_info, client, agent):
        self.client = client
        self.location_info = location_info
        self.agent = agent
