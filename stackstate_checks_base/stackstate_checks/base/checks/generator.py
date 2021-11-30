
from . import AgentCheck


class GeneratorCommand(object):
    def __init__(self):
        pass


class Component(GeneratorCommand):
    def __init__(self, id, type, data, streams=None, checks=None):
        self.id = id
        self.type = type
        self.data = data
        self.streams = streams
        self.checks = checks


class Relation(GeneratorCommand):
    def __init__(self, source, target, type, data, streams=None, checks=None):
        self.source = source
        self.target = target
        self.type = type
        self.data = data
        self.streams = streams
        self.checks = checks


class StartSnapshot(GeneratorCommand):
    def __init__(self):
        pass


class StopSnapshot(GeneratorCommand):
    def __init__(self):
        pass


class ServiceCheck(GeneratorCommand):
    def __init__(self, name, status, tags=None, hostname=None, message=None):
        self.name = name
        self.status = status
        self.tags = tags
        self.hostname = hostname
        self.message = message


def with_service_check(generator, service_name, tags=None, hostname=None):
    service_check_emitted = False

    try:
        for v in generator:
            if type(v) is ServiceCheck:
                service_check_emitted = True
            yield v

        if not service_check_emitted:
            yield ServiceCheck(service_name, AgentCheck.OK, tags, hostname)
    finally:
        if not service_check_emitted:
            yield ServiceCheck(service_name, AgentCheck.CRITICAL, tags, hostname)


class GeneratorAgentCheck(AgentCheck):
    def __init__(self, *args, **kwargs):
        super(GeneratorAgentCheck, self).__init__(*args, **kwargs)

    def generator_check(self, instance):
        raise NotImplementedError

    def check(self, instance):
        pass

