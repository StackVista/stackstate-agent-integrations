from six import with_metaclass
import flatten_dict


def dot_reducer(key1, key2):
    if key1 is None:
        return key2
    else:
        return "{}.{}".format(key1, key2)


class ResourceRegistry(type):

    REGISTRY = {"global": {}, "regional": {}}
    CLOUDTRAIL = {}

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        """
            Here the name of the class is used as key but it could be any class
            parameter.
        """
        if "??" not in [new_cls.API, new_cls.API_TYPE]:
            cls.REGISTRY[new_cls.API_TYPE][new_cls.API] = new_cls
        if "??" != new_cls.EVENT_SOURCE and new_cls.CLOUDTRAIL_EVENTS is not None:
            key = new_cls.EVENT_SOURCE
            if new_cls.API_VERSION != "??":
                key = new_cls.API_VERSION + "-" + new_cls.EVENT_SOURCE
            # dual implementation (we will deprecate one soon)
            if isinstance(new_cls.CLOUDTRAIL_EVENTS, dict):
                cls.CLOUDTRAIL.update({key: new_cls.CLOUDTRAIL_EVENTS})
            elif isinstance(new_cls.CLOUDTRAIL_EVENTS, list):
                cls.CLOUDTRAIL.update({key: {event["event_name"]: new_cls for event in new_cls.CLOUDTRAIL_EVENTS}})
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
    API_VERSION = "??"
    CLOUDTRAIL_EVENTS = None

    def __init__(self, location_info, client, agent):
        self.client = client
        self.agent = agent
        self.location_info = location_info

    def get_delete_ids(self):
        return self.agent.delete_ids

    def emit_component(self, id, type, data):
        if type[:4] == "aws.":
            raise Exception("Component types must not include the COMPONENT_TYPE variable in the name")
        self.agent.component(self.location_info, id, ".".join([self.COMPONENT_TYPE, type]), data)

    def emit_deletion(self, id):
        self.agent.delete(id)

    def emit_relation(self, source, target, type, data):
        self.agent.relation(source, target, type, data)

    def process_all(self, filter=None):
        raise NotImplementedError

    def process_delete_by_name(self, name):
        id = self.agent.create_arn(self.CLOUDFORMATION_TYPE, self.location_info, name)
        self.emit_deletion(id)
        return id

    def process_cloudtrail_event(self, event, seen):
        event_name = event.get("eventName")
        # TODO once we got rid of the old wat of processing the filtering becomes unnecessary
        handlers = list(filter(lambda rec: rec.get("event_name") == event_name, self.CLOUDTRAIL_EVENTS))
        if len(handlers) > 0:
            handler = handlers[0]
            path = handler.get("path")
            processor = handler.get("processor")
            if path and processor:
                flat = flatten_dict.flatten(event, dot_reducer, enumerate_types=(list,))
                id = flat.get(handler["path"])
                if id and id not in seen:
                    processor(self, id)
                    seen.add(id)
            elif processor:
                processor(self, event, seen)
            else:
                self.agent.warning("The API {} should handle CloudTrail event {}".format(self.API, event_name))
