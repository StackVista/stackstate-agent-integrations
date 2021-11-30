# -*- coding: utf-8 -*-

# (C) StackState, Inc. 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.checks import AgentCheck, TopologyInstance


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
    except:
        if not service_check_emitted:
            yield ServiceCheck(service_name, AgentCheck.CRITICAL, tags, hostname)


def with_topology_snapshot(generator):
    stop_emitted = False

    yield StartSnapshot()

    for v in generator:
        # Making sure we do not emit start/stopsnapshot twice
        if type(v) is StartSnapshot:
            continue
        elif type(v) is StopSnapshot:
            if stop_emitted:
                continue
            stop_emitted = True

        yield v

    if not stop_emitted:
        yield StopSnapshot()


def validate_snapshot(generator):
    yield from generator

class UnrecognizedCommandException(Exception):
    pass


class GeneratorAgentCheck(AgentCheck):
    def __init__(self, *args, **kwargs):
        super(GeneratorAgentCheck, self).__init__(*args, **kwargs)

    def generator_check(self, instance):
        raise NotImplementedError

    def check(self, instance):
        for command in self.generator_check(instance):
            if type(command) is ServiceCheck:
                self.service_check(command.name, command.status, command.tags, command.hostname, command.message)
            elif type(command) is Component:
                self.component(command.id, command.type, command.data, command.streams, command.checks)
            elif type(command) is Relation:
                self.relation(command.source, command.target, command.type, command.data, command.streams,
                              command.checks)
            elif type(command) is StartSnapshot:
                self.start_snapshot()
            elif type(command) is StopSnapshot:
                self.stop_snapshot()
            else:
                print("Wrong command")
                raise UnrecognizedCommandException("Unknown command" + type(command))


class GeneratorTestCheck(GeneratorAgentCheck):
    def __init__(self, generator, *args, **kwargs):
        super(GeneratorTestCheck, self).__init__(*args, **kwargs)
        self.generator = generator

    def generator_check(self, instance):
        return self.generator


def exception_generator():
    raise NotImplementedException
    yield StartSnapshot()


class TestWithServiceCheck:
    def test_ok_on_complete(self, aggregator):
        check = GeneratorTestCheck(
            with_service_check([], "name")
        )

        check.check(None)
        aggregator.assert_service_check("name", status=AgentCheck.OK)
        assert len(aggregator.service_checks("name")) == 1

    def test_no_ok_when_emitted(self, aggregator):
        check = GeneratorTestCheck(
            with_service_check([ServiceCheck("name", AgentCheck.WARNING)], "name")
        )

        check.check(None)
        aggregator.assert_service_check("name", status=AgentCheck.WARNING)
        assert len(aggregator.service_checks("name")) == 1

    def test_critical_on_exception(self, aggregator):
        check = GeneratorTestCheck(
            with_service_check(exception_generator(), "name")
        )

        check.check(None)
        aggregator.assert_service_check("name", status=AgentCheck.CRITICAL)
        assert len(aggregator.service_checks("name")) == 1


class GeneratorTopologyCheck(GeneratorTestCheck):
    def __init__(self, generator, key=None, *args, **kwargs):
        instances = [{'a': 'b'}]
        super(GeneratorTopologyCheck, self).__init__(generator, "test", {}, instances, *args, **kwargs)
        self.key = key or TopologyInstance("mytype", "someurl")

    def get_instance_key(self, instance):
        return self.key


class TestWithTopologySnapshot:
    def test_snapshot_generated(self, topology):
        check = GeneratorTopologyCheck(
            with_service_check(
                with_topology_snapshot(
                    []
                ),
                "name"
            )
        )

        check.run()
        # assert snapshotting occurred
        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)

    def test_no_stop_snapshot_on_exception(self, topology, aggregator):
        check = GeneratorTopologyCheck(
            with_service_check(
                with_topology_snapshot(
                    exception_generator()
                ),
                "name"
            )
        )

        check.run()
        aggregator.assert_service_check("name", status=AgentCheck.CRITICAL)
        assert len(aggregator.service_checks("name")) == 1

        topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=False)












class GeneratorExampleCheckImperative(AgentCheck):
    def __init__(self, *args, **kwargs):
        super(GeneratorExampleCheckPy3, self).__init__(*args, **kwargs)

    def get_instance_key(self, instance):
        return TopologyInstance("mytype", "someurl")

    def check(self, instance):
        self.start_snapshot()
        try:
            self.component("id1", "type", {})
            self.stop_snapshot()
            self.service_check("check", AgentCheck.OK)
        except:
            self.service_check("check", AgentCheck.CRITICAL)


# I want to:
# - Write pure functions instead of side-effecting code
# - Be able to bracket start/stop snapshot call
# - Be able to write out a service check value only once, defaulting to OK/CRITICAL upon success/exception











class GeneratorExampleCheckGenerator(GeneratorAgentCheck):
    def __init__(self, *args, **kwargs):
        super(GeneratorExampleCheckPy3, self).__init__(*args, **kwargs)

    def get_instance_key(self, instance):
        return TopologyInstance("mytype", "someurl")

    def generator_check(self, instance):
        yield StartSnapshot()
        yield Component("id1", "type", {})
        yield StopSnapshot()
















class GeneratorExampleCheckPy3(GeneratorAgentCheck):
    def __init__(self, *args, **kwargs):
        super(GeneratorExampleCheckPy3, self).__init__(*args, **kwargs)

    def get_instance_key(self, instance):
        return TopologyInstance("mytype", "someurl")

    def components(self):
        # Fetch data here
        comp_ids = ["id1", "id2"]

        for compId in comp_ids:
            yield Component(compId, "type", {})

    def relations(self):
        yield Relation("id1", "id2", "type", {})

    def topology(self):
        yield from self.components()
        yield from self.relations()

    def generator_check(self, instance):
        yield from (
            with_service_check(
                validate_snapshot(
                    with_topology_snapshot(
                        self.topology()
                    ),
                ),
                "my-service-check"
            )
        )

# Combinators:
# with_service_check(generator): Generator ==  Produce service_check OK on sompletion, CRITICAL on failure. Do not produce when the user already produced a value
# with_topology_snapshot(generator): Generator ==  Make sure start/stop snapshot are generated, but omit sotp if there is an exception. Do not send duplicate elements
# validate_snapshot(generator): Generator == Validate whether all relations produced have a component, and whether we are not creating duplicate component/relation ids


## Pros
# - All generated data is passed through an iterator so can be acted upon and analyzed, no side-effects!
# - Supports bounded-memory model of iteratively producing data to keep memory pressure low
# - Explicit handling of exceptions becomes possible
# - Can exist next to current api
# - Natural use of python capabilities

## Cons
# - `yield from` not support in python 2, has for become: for x in <expr>: yield x








class TestExample:
    def test_snapshot_generated(self, topology):
        instances = [{'a': 'b'}]
        check = GeneratorExampleCheckPy3("test", {}, instances)

        assert check.run() == ''
        # assert snapshotting occurred
        topology.assert_snapshot(check.check_id, check.get_instance_key(None),
                                 start_snapshot=True,
                                 stop_snapshot=True,
                                 components=[
                                     {
                                         'id': 'id1',
                                         'type': 'type',
                                         'data': {
                                             u"tags": ['integration-type:mytype',
                                                       'integration-url:someurl']
                                         }
                                     }
                                     , {
                                         'id': 'id2',
                                         'type': 'type',
                                         'data': {
                                             u"tags": ['integration-type:mytype',
                                                       'integration-url:someurl']
                                         }
                                     }
                                 ],
                                 relations=[
                                     {
                                         'source_id': 'id1',
                                         'target_id': 'id2',
                                         'type': 'type',
                                         'data': {}
                                     }
                                 ])

        # class TopologyCheck(GeneratorAgentCheck):
        #     def __init__(self, key=None, *args, **kwargs):
        #         super(TopologyCheck, self).__init__(*args, **kwargs)
        #         self.key = key or TopologyInstance("mytype", "someurl")
        #
        #     def get_instance_key(self, instance):
        #         return self.key
        #
        #
        # class TopologyAutoSnapshotCheck(TopologyCheck):
        #     def __init__(self):
        #         instances = [{'a': 'b'}]
        #         super(TopologyAutoSnapshotCheck, self) \
        #             .__init__(TopologyInstance("mytype", "someurl", with_snapshots=True), "test", {}, instances)
        #
        #     def check(self, instance):
        #         pass
        #
        #
        # class TopologyBrokenCheck(TopologyAutoSnapshotCheck):
        #     def __init__(self):
        #         super(TopologyBrokenCheck, self).__init__()
        #
        #     def check(self, instance):
        #         raise Exception("some error in my check")
        #
        #
        # class HealthCheck(AgentCheck):
        #     def __init__(self,
        #                  stream=HealthStream(HealthStreamUrn("source", "stream_id"), "sub_stream"),
        #                  instance={'collection_interval': 15, 'a': 'b'},
        #                  *args, **kwargs):
        #         instances = [instance]
        #         self.stream = stream
        #         super(HealthCheck, self).__init__("test", {}, instances)
        #
        #     def get_health_stream(self, instance):
        #         return self.stream
        #
        #     def check(self, instance):
        #         return
        #
        #
        # class HealthCheckMainStream(AgentCheck):
        #     def __init__(self, stream=HealthStream(HealthStreamUrn("source", "stream_id")), *args, **kwargs):
        #         instances = [{'collection_interval': 15, 'a': 'b'}]
        #         self.stream = stream
        #         super(HealthCheckMainStream, self).__init__("test", {}, instances)
        #
        #     def get_health_stream(self, instance):
        #         return self.stream
        #
        #     def check(self, instance):
        #         return
        #
        #
        # TEST_STATE = {
        #     'string': 'string',
        #     'int': 1,
        #     'float': 1.0,
        #     'bool': True,
        #     'list': ['a', 'b', 'c'],
        #     'dict': {'a': 'b'}
        # }
        #
        #
        # class TopologyStatefulCheck(TopologyAutoSnapshotCheck):
        #     def __init__(self):
        #         super(TopologyStatefulCheck, self).__init__()
        #
        #     @staticmethod
        #     def get_agent_conf_d_path():
        #         return "./test_data"
        #
        #     def check(self, instance):
        #         instance.update({'state': TEST_STATE})
        #
        #
        # class TopologyStatefulCheckStateLocation(TopologyAutoSnapshotCheck):
        #     def __init__(self):
        #         instances = [{"state_location": "./test_data_2"}]
        #         super(TopologyAutoSnapshotCheck, self) \
        #             .__init__(TopologyInstance("mytype", "https://some.type.url", with_snapshots=True), "test", {}, instances)
        #
        #     def check(self, instance):
        #         instance.update({'state': TEST_STATE})
        #
        #
        # class TopologyStatefulStateDescriptorCleanupCheck(TopologyAutoSnapshotCheck):
        #     def __init__(self):
        #         instances = [{'a': 'b'}]
        #         super(TopologyAutoSnapshotCheck, self) \
        #             .__init__(TopologyInstance("mytype", "https://some.type.url", with_snapshots=True), "test", {}, instances)
        #
        #     @staticmethod
        #     def get_agent_conf_d_path():
        #         return "./test_data"
        #
        #     def check(self, instance):
        #         instance.update({'state': TEST_STATE})
        #
        #
        # class TopologyClearStatefulCheck(TopologyStatefulCheck):
        #     def __init__(self):
        #         super(TopologyClearStatefulCheck, self).__init__()
        #
        #     def check(self, instance):
        #         instance.update({'state': None})
        #
        #
        # class TopologyBrokenStatefulCheck(TopologyStatefulCheck):
        #     def __init__(self):
        #         super(TopologyBrokenStatefulCheck, self).__init__()
        #
        #     def check(self, instance):
        #         instance.update({'state': TEST_STATE})
        #
        #         raise Exception("some error in my check")
        #
        #
        # class IdentifierMappingTestAgentCheck(TopologyCheck):
        #     def __init__(self):
        #         instances = [
        #             {
        #                 'identifier_mappings':
        #                     {
        #                         'host': {'field': 'url', 'prefix': 'urn:computer:/'},
        #                         'vm': {'field': 'name', 'prefix': 'urn:computer:/'}
        #                     }
        #             }
        #         ]
        #         super(IdentifierMappingTestAgentCheck, self)\
        #             .__init__(TopologyInstance("host", "someurl"), "test", {}, instances)
        #
        #     def check(self, instance):
        #         pass
        #
        #
        # class NestedIdentifierMappingTestAgentCheck(TopologyCheck):
        #     def __init__(self):
        #         instances = [
        #             {
        #                 'identifier_mappings':
        #                     {
        #                         'host': {'field': 'x.y.z.url', 'prefix': 'urn:computer:/'}
        #                     }
        #             }
        #         ]
        #         super(NestedIdentifierMappingTestAgentCheck, self)\
        #             .__init__(TopologyInstance("host", "someurl"), "test", {}, instances)
        #
        #     def check(self, instance):
        #         pass
        #
        #
        # class StateSchema(Model):
        #     offset = IntType(required=True)
        #
        #
        # class CheckInstanceSchema(Model):
        #     a = StringType(required=True)
        #     state = ModelType(StateSchema, required=True, default=StateSchema({'offset': 0}))
        #
        #
        # class TopologyStatefulSchemaCheck(TopologyStatefulCheck):
        #     INSTANCE_SCHEMA = CheckInstanceSchema
        #
        #     def check(self, instance):
        #         print(instance.a)
        #         instance.state.offset = 20
        #
        #
        # class TagsAndConfigMappingAgentCheck(TopologyCheck):
        #     def __init__(self, include_instance_config):
        #         instance = {
        #             'identifier_mappings': {
        #                 'host': {'field': 'url', 'prefix': 'urn:computer:/'},
        #                 'vm': {'field': 'name', 'prefix': 'urn:computer:/'}
        #             },
        #         }
        #
        #         if include_instance_config:
        #             instance.update({
        #                 'stackstate-layer': 'instance-stackstate-layer',
        #                 'stackstate-environment': 'instance-stackstate-environment',
        #                 'stackstate-domain': 'instance-stackstate-domain',
        #                 'stackstate-identifier': 'instance-stackstate-identifier',
        #                 'stackstate-identifiers': 'urn:process:/mapped-identifier:0:1234567890, \
        #                     urn:process:/mapped-identifier:1:1234567890 \
        #                     urn:process:/mapped-identifier:2:1234567890  ,  \
        #                     urn:process:/mapped-identifier:3:1234567890'
        #             })
        #
        #         super(TagsAndConfigMappingAgentCheck, self) \
        #             .__init__(TopologyInstance("host", "someurl"), "test", {}, [instance])
        #
        #     def check(self, instance):
        #         pass
        #
        #
        # class TestTagsAndConfigMapping:
        #     def generic_tags_and_config_snapshot(self, topology, include_instance_config, include_tags, extra_data=None):
        #         check = TagsAndConfigMappingAgentCheck(include_instance_config)
        #         data = {}
        #         if include_tags:
        #             data = {
        #                 'tags': ['stackstate-layer:tag-stackstate-layer',
        #                          'stackstate-environment:tag-stackstate-environment',
        #                          'stackstate-domain:tag-stackstate-domain',
        #                          'stackstate-identifier:urn:process:/mapped-identifier:001:1234567890',
        #                          'stackstate-identifiers:\
        #                              urn:process:/mapped-identifier:0:1234567890, \
        #                              urn:process:/mapped-identifier:1:1234567890 \
        #                              urn:process:/mapped-identifier:2:1234567890  ,  \
        #                              urn:process:/mapped-identifier:3:1234567890'
        #                          ]
        #             }
        #         if extra_data:
        #             data.update(extra_data)
        #         check.component("my-id", "host", data)
        #         return topology.get_snapshot(check.check_id)['components'][0]
        #
        #     def test_comma_and_spaces_regex(self):
        #         check = TagsAndConfigMappingAgentCheck(True)
        #         assert check.split_on_commas_and_spaces('a, b, c,d,e f g h, i , j ,k   ') == \
        #                ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
        #         assert check.split_on_commas_and_spaces('a,  ,  ,, , j ,k   ') == ["a", "j", "k"]
        #         assert check.split_on_commas_and_spaces(',,,,,,,,,,,           ,,,,,,,,,') == []
        #         assert check.split_on_commas_and_spaces('') == []
        #         assert check.split_on_commas_and_spaces('urn:test:0:123,urn:test:1:123,urn:test:2:123') == \
        #                ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]
        #         assert check.split_on_commas_and_spaces('urn:test:0:123 urn:test:1:123 urn:test:2:123') == \
        #                ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]
        #         assert check.split_on_commas_and_spaces('urn:test:0:123 urn:test:1:123,urn:test:2:123') == \
        #                ["urn:test:0:123", "urn:test:1:123", "urn:test:2:123"]
        #
        #     def test_mapping_config_and_tags(self):
        #         # We are create config variables with and without instance config
        #         check_include_config = TagsAndConfigMappingAgentCheck(True)
        #         check_exclude_config = TagsAndConfigMappingAgentCheck(False)
        #
        #         """
        #             We are testing the following:
        #                 Config + No Data == Config Result is not in a Array
        #                 Config + No Data, True == Config Result is in a Array
        #                 Config + Data == Data Result is not in a Array (Must not be config)
        #                 Config + Data, True == Data Result is in a Array (Must not be config)
        #                 No Config + No Data + Default Value == Result must be the default value and not a Array
        #                 No Config + No Data + Default Value, True == Result must be the default value in a Array
        #             Tags must overwrite configs
        #         """
        #         def generic_mapping_test(target, origin, default_value=None):
        #             data = {
        #                 'tags': ['stackstate-layer:tag-stackstate-layer',
        #                          'stackstate-environment:tag-stackstate-environment',
        #                          'stackstate-domain:tag-stackstate-domain',
        #                          'stackstate-identifier:tag-stackstate-identifier',
        #                          'stackstate-identifiers:tag-stackstate-identifiers']
        #             }
        #
        #             # Create a copy of the data object
        #             data_without_target = copy.deepcopy(data)
        #
        #             # Remove the current target from the tags array as the result should not contain that tag
        #             data_without_target.get("tags").remove(target + ":tag-" + target)
        #
        #             # Include instance config in the tests
        #             assert check_include_config._map_config_and_tags({}, target, origin) == \
        #                    {origin: 'instance-' + target}
        #             assert check_include_config._map_config_and_tags({}, target, origin, True) == \
        #                    {origin: ['instance-' + target]}
        #             assert check_include_config._map_config_and_tags(copy.deepcopy(data), target, origin) == \
        #                    {origin: 'tag-' + target, 'tags': data_without_target['tags']}
        #             assert check_include_config._map_config_and_tags(copy.deepcopy(data), target, origin, True) == \
        #                    {origin: ['tag-' + target], 'tags': data_without_target['tags']}
        #
        #             # Exclude the instance config in the tests
        #             assert check_exclude_config._map_config_and_tags({}, target, origin) == {}
        #             assert check_exclude_config._map_config_and_tags({}, target, origin, True) == {}
        #             assert check_exclude_config._map_config_and_tags(copy.deepcopy(data), target, origin) == \
        #                    {origin: 'tag-' + target, 'tags': data_without_target['tags']}
        #             assert check_exclude_config._map_config_and_tags(copy.deepcopy(data), target, origin, True) == \
        #                    {origin: ['tag-' + target], 'tags': data_without_target['tags']}
        #
        #             # Default Config
        #             assert check_exclude_config._map_config_and_tags({}, target, origin, False, False, default_value) == \
        #                    {origin: default_value}
        #             assert check_exclude_config._map_config_and_tags({}, target, origin, True, False, default_value) == \
        #                    {origin: [default_value]}
        #
        #             # Return direct value & Return direct value arrays test
        #             assert check_exclude_config._map_config_and_tags(copy.deepcopy(data), target, origin, False, True) == \
        #                    'tag-' + target
        #             assert check_include_config._map_config_and_tags(copy.deepcopy(data), target, origin, False, True) == \
        #                    'tag-' + target
        #             assert check_exclude_config._map_config_and_tags({}, target, origin, False, True) == \
        #                    {}
        #             assert check_include_config._map_config_and_tags({}, target, origin, False, True) == \
        #                    'instance-' + target
        #             assert check_exclude_config._map_config_and_tags(copy.deepcopy(data), target, origin, True, True) == \
        #                    ['tag-' + target]
        #             assert check_include_config._map_config_and_tags(copy.deepcopy(data), target, origin, True, True) == \
        #                    ['tag-' + target]
        #             assert check_exclude_config._map_config_and_tags({}, target, origin, True, True) == \
        #                    []
        #             assert check_include_config._map_config_and_tags({}, target, origin, True, True) == \
        #                    ['instance-' + target]
        #
        #         # We are testing the environment, layer and domain for all the use cases
        #         generic_mapping_test("stackstate-environment", "environments", "default-environment")
        #         generic_mapping_test("stackstate-layer", "layer", "default-layer")
        #         generic_mapping_test("stackstate-domain", "domain", "default-domain")
        #         generic_mapping_test("stackstate-identifier", "identifier", "default-identifier")
        #
        #     def test_instance_only_config(self, topology):
        #         component = self.generic_tags_and_config_snapshot(topology, True, False)
        #         assert component["data"]["layer"] == "instance-stackstate-layer"
        #         assert component["data"]["environments"] == ["instance-stackstate-environment"]
        #         assert component["data"]["domain"] == "instance-stackstate-domain"
        #
        #     def test_tags_only(self, topology):
        #         component = self.generic_tags_and_config_snapshot(topology, False, True)
        #         assert component["data"]["layer"] == "tag-stackstate-layer"
        #         assert component["data"]["environments"] == ["tag-stackstate-environment"]
        #         assert component["data"]["domain"] == "tag-stackstate-domain"
        #
        #     def test_tags_overwrite_config(self, topology):
        #         component = self.generic_tags_and_config_snapshot(topology, True, True)
        #         assert component["data"]["layer"] == "tag-stackstate-layer"
        #         assert component["data"]["environments"] == ["tag-stackstate-environment"]
        #         assert component["data"]["domain"] == "tag-stackstate-domain"
        #
        #     def test_identifier_config(self, topology):
        #         component = self.generic_tags_and_config_snapshot(topology, True, False, {
        #             'identifiers': ['urn:process:/original-identifier:0:1234567890']
        #         })
        #         assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890',
        #                                                     'instance-stackstate-identifier']
        #
        #     def test_identifier_tags(self, topology):
        #         component = self.generic_tags_and_config_snapshot(topology, True, True, {
        #             'identifiers': [
        #                 'urn:process:/original-identifier:0:1234567890'
        #             ],
        #             'url': '1234567890'
        #         })
        #         assert component["data"]["identifiers"] == ['urn:process:/original-identifier:0:1234567890',
        #                                                     'urn:computer:/1234567890',
        #                                                     'urn:process:/mapped-identifier:0:1234567890',
        #                                                     'urn:process:/mapped-identifier:1:1234567890',
        #                                                     'urn:process:/mapped-identifier:2:1234567890',
        #                                                     'urn:process:/mapped-identifier:3:1234567890',
        #                                                     'urn:process:/mapped-identifier:001:1234567890']
        #
        #
        # class TestBaseSanitize:
        #     def test_ensure_homogeneous_list(self):
        #         """
        #         Testing the functionality of _ensure_homogeneous_list to ensure that agent checks can only produce homogeneous
        #         lists
        #         """
        #         check = AgentCheck()
        #
        #         # list of ints
        #         check._ensure_homogeneous_list([1, 2, 3])
        #         # list of booleans
        #         check._ensure_homogeneous_list([True, True, False])
        #         # list of string
        #         check._ensure_homogeneous_list(['a', 'b', 'c'])
        #         # list of string + text_type
        #         check._ensure_homogeneous_list(['a', u'b', '®'])
        #         # list of floats
        #         check._ensure_homogeneous_list([1.0, 2.0, 3.0])
        #         # list of dicts
        #         check._ensure_homogeneous_list([{'a': 'b'}, {'a': 'c'}, {'a': 'd'}])
        #         # list of mixed dicts
        #         check._ensure_homogeneous_list([{'a': 'b'}, {'c': []}, {'d': False}])
        #         # list of lists
        #         check._ensure_homogeneous_list([[1], [2], [3]])
        #         # list of mixed lists
        #         check._ensure_homogeneous_list([[1], ['b'], [True], [{'c': 'd'}]])
        #         # list of sets
        #         check._ensure_homogeneous_list([set([1]), set([2]), set([3])])
        #         # list of mixed sets
        #         check._ensure_homogeneous_list([set([1]), set(['b']), set([True]), set([1.5])])
        #
        #         def exeception_case(list, expected_types):
        #             with pytest.raises(TypeError) as e:
        #                 check._ensure_homogeneous_list(list)
        #
        #             assert str(e.value) == "List: {0}, is not homogeneous, it contains the following types: {1}"\
        #                 .format(list, expected_types)
        #
        #         # list of ints and strings
        #         exeception_case([1, '2', 3, '4'], {str, int})
        #         # list of int, string, float, bool
        #         exeception_case([1, '2', 3.5, True], {str, int, float, bool})
        #         # list of ints and floats
        #         exeception_case([1, 1.5, 2, 2.5], {int, float})
        #         # list of ints and bools
        #         exeception_case([1, True, 2, False], {int, bool})
        #         # list of ints and dicts
        #         exeception_case([1, {'a': True}, 2, {'a': False}], {int, dict})
        #         # list of strings and lists
        #         exeception_case(['a', [True], 'b', [False]], {str, list})
        #         # list of strings and sets
        #         exeception_case(['a', set([True]), 'b', set([False])], {str, set})
        #         # list of strings, sets and dicts
        #         exeception_case(['a', set([True]), {'a': True}, 'b', set([False])], {str, set, dict})
        #
        #         # list of strings and dicts
        #         exeception_case(['a', {'a': True}, 'b', {'a': False}], {str, dict})
        #         # list of strings and floats
        #         exeception_case(['a', 1.5, 'b', 2.5], {str, float})
        #         # list of strings and bools
        #         exeception_case(['a', True, 'b', False], {str, bool})
        #         # list of strings and lists
        #         exeception_case(['a', [True], 'b', [False]], {str, list})
        #         # list of strings and sets
        #         exeception_case(['a', set([True]), 'b', set([False])], {str, set})
        #
        #         # list of lists and dicts
        #         exeception_case([['a'], {'a': True}, ['b'], {'a': False}], {list, dict})
        #         # list of lists and sets
        #         exeception_case([['a'], set(['a']), ['b'], set(['b'])], {list, set})
        #
        #     def test_ensure_homogeneous_list_check_api(self):
        #         """
        #         Testing the functionality of _ensure_homogeneous_list, but we're calling it through the check api to ensure that
        #         topology and telemetry is not created when the data contains a non-homogeneous list
        #         """
        #         check = AgentCheck()
        #
        #         # ensure nothing is created for components with non-homogeneous lists
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
        #                 "mixedlist": ['a', 'b', 'c', 4]}
        #         assert check.component("my-id", "my-type", data) is None
        #         # ensure nothing is created for relations with non-homogeneous lists
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
        #                 "mixedlist": ['a', 'b', 'c', 4]}
        #         assert check.relation("source-id", "target-id", "my-type", data) is None
        #         # ensure that a schematics data error is thrown for events with non-homogeneous tags
        #         with pytest.raises(DataError):
        #             event = {
        #                 "timestamp": 123456789,
        #                 "event_type": "new.event",
        #                 "source_type_name": "new.source.type",
        #                 "msg_title": "new test event",
        #                 "aggregation_key": "test.event",
        #                 "msg_text": "test event test event",
        #                 "tags": ['a', 'b', 'c', 4],
        #             }
        #             assert check.event(event) is None
        #         # ensure that a schematics data error is thrown for topology events with non-homogeneous tags
        #         with pytest.raises(DataError):
        #             event = {
        #                 "timestamp": 123456789,
        #                 "source_type_name": "new.source.type",
        #                 "msg_title": "new test event",
        #                 "aggregation_key": "test.event",
        #                 "msg_text": "test event test event",
        #                 "tags": ['a', 'b', 'c', 4],
        #                 "context": {
        #                     "element_identifiers": ["urn:test:/value"],
        #                     "source": "test source",
        #                     "category": "test category",
        #                 }
        #             }
        #             assert check.event(event) is None
        #         # ensure that a nothing is created for topology events with non-homogeneous tags in the data section
        #         event = {
        #             "timestamp": 123456789,
        #             "source_type_name": "new.source.type",
        #             "msg_title": "new test event",
        #             "aggregation_key": "test.event",
        #             "msg_text": "test event test event",
        #             "tags": ['a', 'b', 'c', 'd'],
        #             "context": {
        #                 "element_identifiers": ["urn:test:/value"],
        #                 "source": "test source",
        #                 "category": "test category",
        #                 "data": {
        #                     "mixedlist": ['a', 'b', 'c', 4]
        #                 }
        #             }
        #         }
        #         assert check.event(event) is None
        #
        #     @pytest.mark.skipif(sys.platform.startswith('win') and sys.version_info < (3, 7),
        #                         reason='ordered set causes erratic error failures on windows')
        #     def test_ensure_string_only_keys(self):
        #         """
        #         Testing the functionality of _ensure_string_only_keys, but we're calling _sanitize to deal with multi-tier
        #         dictionaries
        #         """
        #         check = AgentCheck()
        #
        #         # valid dictionaries
        #         check._sanitize({'a': 1, 'c': True, 'e': 'f'})
        #         check._sanitize({'a': {'b': {'c': True}}, 'e': 1.2})
        #         check._sanitize({'a': {'b': {'c': {'e': ['f', 'g']}}}})
        #
        #         def exeception_case(dictionary, error_type_set):
        #             with pytest.raises(TypeError) as e:
        #                 check._sanitize(dictionary)
        #
        #             assert "contains keys which are not string or {0}: {1}".format(text_type, error_type_set) in str(e.value)
        #
        #         # dictionary with int as keys
        #         exeception_case({'a': 'b', 'c': 'd', 1: 'f'}, {str, int})
        #         exeception_case({'a': {'b': {1: 'd'}}, 'e': 'f'}, {int})  # inner dictionary only has a int key
        #         exeception_case({'a': {'b': {'c': {1: 'f'}}}}, {int})  # inner dictionary only has a int key
        #         # dictionary with None as keys
        #         exeception_case({'a': 'b', 'c': 'd', None: 'f'}, {str, type(None)})
        #         exeception_case({'a': {'b': {None: 'd'}}, 'e': 'f'}, {type(None)})  # inner dictionary only has a None key
        #         exeception_case({'a': {'b': {'c': {None: 'f'}}}}, {type(None)})  # inner dictionary only has a None key
        #         # dictionary with list as keys
        #         exeception_case({'a': 'b', 'c': 'd', True: 'f'}, {str, bool})
        #         exeception_case({'a': {'b': {True: 'd'}}, 'e': 'f'}, {bool})  # inner dictionary only has a bool key
        #         exeception_case({'a': {'b': {'c': {True: 'f'}}}}, {bool})  # inner dictionary only has a bool key
        #
        #     def test_ensure_string_only_keys_check_functions(self):
        #         """
        #         Testing the functionality of _ensure_string_only_keys, but we're calling it through the check api to ensure that
        #         topology and telemetry is not created when a dictionary contains a non-string key
        #         """
        #         check = AgentCheck()
        #         # ensure nothing is created for components with non-string key dicts
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
        #                 "nonstringkeydict": {'a': 'b', 3: 'c'}}
        #         assert check.component("my-id", "my-type", data) is None
        #         # ensure nothing is created for relations with non-string key dicts
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"},
        #                 "nonstringkeydict": {'a': 'b', 3: 'c'}}
        #         assert check.relation("source-id", "target-id", "my-type", data) is None
        #         # ensure that a nothing is created for topology events with non-string key dicts in the data section
        #         event = {
        #             "timestamp": 123456789,
        #             "source_type_name": "new.source.type",
        #             "msg_title": "new test event",
        #             "aggregation_key": "test.event",
        #             "msg_text": "test event test event",
        #             "tags": ['a', 'b', 'c', 'd'],
        #             "context": {
        #                 "element_identifiers": ["urn:test:/value"],
        #                 "source": "test source",
        #                 "category": "test category",
        #                 "data": {"nonstringkeydict": {'a': 'b', 3: 'c'}}
        #             }
        #         }
        #         assert check.event(event) is None
        #
        #
        # class TestTopology:
        #     def test_component(self, topology):
        #         check = TopologyCheck()
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        #         created_component = check.component("my-id", "my-type", data)
        #         assert data['key'] == created_component['data']['key']
        #         assert data['intlist'] == created_component['data']['intlist']
        #         assert data['nestedobject'] == created_component['data']['nestedobject']
        #         assert created_component['id'] == 'my-id'
        #         assert created_component['type'] == 'my-type'
        #         topology.assert_snapshot(check.check_id, check.key, components=[created_component])
        #
        #     def test_relation(self, topology):
        #         check = TopologyCheck()
        #         data = {"key": "value", "intlist": [1], "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        #         created_relation = check.relation("source-id", "target-id", "my-type", data)
        #         assert data['key'] == created_relation['data']['key']
        #         assert data['intlist'] == created_relation['data']['intlist']
        #         assert data['nestedobject'] == created_relation['data']['nestedobject']
        #         assert created_relation['source_id'] == 'source-id'
        #         assert created_relation['target_id'] == 'target-id'
        #         assert created_relation['type'] == 'my-type'
        #         topology.assert_snapshot(check.check_id, check.key, relations=[created_relation])
        #
        #     def test_auto_snapshotting(self, topology):
        #         check = TopologyAutoSnapshotCheck()
        #         check.run()
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_no_stop_snapshot_on_exception(self, topology):
        #         check = TopologyBrokenCheck()
        #         check.run()
        #         # assert stop snapshot is false when an exception is thrown in check.run()
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=False)
        #
        #     def test_start_snapshot(self, topology):
        #         check = TopologyCheck()
        #         check.start_snapshot()
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True)
        #
        #     def test_stop_snapshot(self, topology):
        #         check = TopologyCheck()
        #         check.stop_snapshot()
        #         topology.assert_snapshot(check.check_id, check.key, stop_snapshot=True)
        #
        #     def test_stateful_check(self, topology, state):
        #         check = TopologyStatefulCheck()
        #         state.assert_state_check(check, expected_pre_run_state=None, expected_post_run_state=TEST_STATE)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_stateful_check_config_location(self, topology, state):
        #         check = TopologyStatefulCheckStateLocation()
        #         state.assert_state_check(check, expected_pre_run_state=None, expected_post_run_state=TEST_STATE)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_stateful_state_descriptor_cleanup_check(self, topology, state):
        #         check = TopologyStatefulStateDescriptorCleanupCheck()
        #         state_descriptor = check._get_state_descriptor()
        #         assert state_descriptor.instance_key == "instance.mytype.https_some.type.url"
        #         assert check._get_instance_key_dict() == {'type': 'mytype', 'url': 'https://some.type.url'}
        #         state.assert_state_check(check, expected_pre_run_state=None, expected_post_run_state=TEST_STATE)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_clear_stateful_check(self, topology, state):
        #         check = TopologyClearStatefulCheck()
        #         # set the previous state and assert the state check function as expected
        #         check.state_manager.set_state(check._get_state_descriptor(), TEST_STATE)
        #         state.assert_state_check(check, expected_pre_run_state=TEST_STATE, expected_post_run_state=None)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_no_state_change_on_exception_stateful_check(self, topology, state):
        #         check = TopologyBrokenStatefulCheck()
        #         # set the previous state and assert the state check function as expected
        #         previous_state = {'my_old': 'state'}
        #         check.state_manager.set_state(check._get_state_descriptor(), previous_state)
        #         state.assert_state_check(check, expected_pre_run_state=previous_state, expected_post_run_state=previous_state)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=False)
        #
        #     def test_stateful_schema_check(self, topology, state):
        #         check = TopologyStatefulSchemaCheck()
        #         # assert the state check function as expected
        #         state.assert_state_check(check, expected_pre_run_state=None,
        #                                  expected_post_run_state=StateSchema({'offset': 20}), state_schema=StateSchema)
        #         # assert auto snapshotting occurred
        #         topology.assert_snapshot(check.check_id, check.key, start_snapshot=True, stop_snapshot=True)
        #
        #     def test_none_data_ok(self, topology):
        #         check = TopologyCheck()
        #         check.component("my-id", "my-type", None)
        #         topology.assert_snapshot(check.check_id, check.key, components=[component("my-id", "my-type",
        #                                                                                   {'tags': ['integration-type:mytype',
        #                                                                                             'integration-url:someurl']
        #                                                                                    })])
        #
        #     def test_illegal_data(self):
        #         check = TopologyCheck()
        #         with pytest.raises(ValueError) as e:
        #             assert check.component("my-id", "my-type", 1)
        #         if PY3:
        #             assert str(e.value) == "Got unexpected <class 'int'> for argument data, expected dictionary or None value"
        #         else:
        #             assert str(e.value) == "Got unexpected <type 'int'> for argument data, expected dictionary or None value"
        #
        #     def test_illegal_data_value(self):
        #         check = TopologyCheck()
        #         with pytest.raises(ValueError) as e:
        #             assert check.component("my-id", "my-type", {"key": {1, 2, 3}})
        #         if PY3:
        #             assert str(e.value) == """Got unexpected <class 'set'> for argument data.key, \
        # expected string, int, dictionary, list or None value"""
        #         else:
        #             assert str(e.value) == """Got unexpected <type 'set'> for argument data.key, \
        # expected string, int, dictionary, list or None value"""
        #
        #     def test_illegal_instance_key_none(self):
        #         check = TopologyCheck()
        #         check.key = None
        #         with pytest.raises(ValueError) as e:
        #             assert check.component("my-id", "my-type", None)
        #         if PY3:
        #             assert str(e.value) == "Got unexpected <class 'str'> for argument get_instance_key(), expected dictionary"
        #         else:
        #             assert str(e.value) == "Got unexpected <type 'str'> for argument get_instance_key(), expected dictionary"
        #
        #     def test_illegal_instance_type(self):
        #         check = TopologyCheck()
        #         check.key = {}
        #         with pytest.raises(ValueError) as e:
        #             assert check.component("my-id", "my-type", None)
        #         if PY3:
        #             assert str(e.value) == """Got unexpected <class 'dict'> for argument get_instance_key(), \
        # expected TopologyInstance, AgentIntegrationInstance or DefaultIntegrationInstance"""
        #         else:
        #             assert str(e.value) == """Got unexpected <type 'dict'> for argument get_instance_key(), \
        # expected TopologyInstance, AgentIntegrationInstance or DefaultIntegrationInstance"""
        #
        #     def test_illegal_instance_key_field_type(self):
        #         check = TopologyCheck()
        #         check.key = TopologyInstance("mytype", 1)
        #         with pytest.raises(ValueError) as e:
        #             assert check.component("my-id", "my-type", None)
        #         assert str(e.value) == "Instance requires a 'url' field of type 'string'"
        #
        #     def test_topology_instance(self, topology):
        #         check = TopologyCheck()
        #         check.key = TopologyInstance("mytype", "myurl")
        #         assert check._get_instance_key_dict() == {"type": "mytype", "url": "myurl"}
        #         check.create_integration_instance()
        #         # assert integration topology is created for topology instances
        #         topo_instances = topology.get_snapshot('mytype:myurl')
        #         assert topo_instances == self.agent_integration_topology('mytype', 'myurl')
        #
        #     def test_agent_integration_instance(self, topology):
        #         check = AgentIntegrationInstanceCheck()
        #         assert check._get_instance_key_dict() == {"type": "agent", "url": "integrations"}
        #         check.create_integration_instance()
        #         # assert integration topology is created for agent integration instances
        #         topo_instances = topology.get_snapshot(check.check_id)
        #         assert topo_instances == self.agent_integration_topology('test', 'integration')
        #
        #     def test_agent_telemetry_instance(self, topology):
        #         check = DefaultInstanceCheck()
        #         assert check._get_instance_key_dict() == {"type": "agent", "url": "integrations"}
        #         check.create_integration_instance()
        #         # assert no integration topology is created for default instances
        #         assert topology._snapshots == {}
        #
        #     def agent_integration_topology(self, type, url):
        #         return {
        #             'components': [
        #                 {
        #                     'data': {
        #                         'cluster': 'stubbed-cluster-name',
        #                         'hostname': 'stubbed.hostname',
        #                         'identifiers': [
        #                             'urn:process:/stubbed.hostname:1:1234567890'
        #                         ],
        #                         'name': 'StackState Agent:stubbed.hostname',
        #                         'tags': sorted([
        #                             'hostname:stubbed.hostname',
        #                             'stackstate-agent',
        #                         ])
        #                     },
        #                     'id': 'urn:stackstate-agent:/stubbed.hostname',
        #                     'type': 'stackstate-agent'
        #                 },
        #                 {
        #                     'data': {
        #                         'checks': [
        #                             {
        #                                 'is_service_check_health_check': True,
        #                                 'name': 'Integration Health',
        #                                 'stream_id': -1
        #                             }
        #                         ],
        #                         'cluster': 'stubbed-cluster-name',
        #                         'service_checks': [
        #                             {
        #                                 'conditions': [
        #                                     {
        #                                         'key': 'host',
        #                                         'value': 'stubbed.hostname'
        #                                     },
        #                                     {
        #                                         'key': 'tags.integration-type',
        #                                         'value': type
        #                                     }
        #                                 ],
        #                                 'name': 'Service Checks',
        #                                 'stream_id': -1
        #                             }
        #                         ],
        #                         'hostname': 'stubbed.hostname',
        #                         'integration': type,
        #                         'name': 'stubbed.hostname:%s' % type,
        #                         'tags': sorted([
        #                             'hostname:stubbed.hostname',
        #                             'integration-type:%s' % type,
        #                         ])
        #                     },
        #                     'id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
        #                     'type': 'agent-integration'
        #                 },
        #                 {
        #                     'data': {
        #                         'checks': [
        #                             {
        #                                 'is_service_check_health_check': True,
        #                                 'name': 'Integration Instance Health',
        #                                 'stream_id': -1
        #                             }
        #                         ],
        #                         'cluster': 'stubbed-cluster-name',
        #                         'service_checks': [
        #                             {
        #                                 'conditions': [
        #                                     {
        #                                         'key': 'host',
        #                                         'value': 'stubbed.hostname'
        #                                     },
        #                                     {
        #                                         'key': 'tags.integration-type',
        #                                         'value': type
        #                                     },
        #                                     {
        #                                         'key': 'tags.integration-url',
        #                                         'value': url
        #                                     }
        #                                 ],
        #                                 'name': 'Service Checks',
        #                                 'stream_id': -1
        #                             }
        #                         ],
        #                         'hostname': 'stubbed.hostname',
        #                         'integration': type,
        #                         'name': '%s:%s' % (type, url),
        #                         'tags': sorted([
        #                             'hostname:stubbed.hostname',
        #                             'integration-type:%s' % type,
        #                             'integration-url:%s' % url
        #                         ])
        #                     },
        #                     'id': 'urn:agent-integration-instance:/stubbed.hostname:%s:%s' % (type, url),
        #                     'type': 'agent-integration-instance'
        #                 },
        #             ],
        #             'instance_key': {
        #                 'type': 'agent',
        #                 'url': 'integrations'
        #             },
        #             'relations': [
        #                 {
        #                     'data': {},
        #                     'source_id': 'urn:stackstate-agent:/stubbed.hostname',
        #                     'target_id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
        #                     'type': 'runs'
        #                 },
        #                 {
        #                     'data': {},
        #                     'source_id': 'urn:agent-integration:/stubbed.hostname:%s' % type,
        #                     'target_id': 'urn:agent-integration-instance:/stubbed.hostname:%s:%s' % (type, url),
        #                     'type': 'has'
        #                 },
        #             ],
        #             'start_snapshot': False,
        #             'stop_snapshot': False
        #         }
        #
        #     def test_component_with_identifier_mapping(self, topology):
        #         """
        #         Test should generate identifier mapping based on the prefix and field value
        #         """
        #         check = IdentifierMappingTestAgentCheck()
        #         data = {"url": "identifier-url", "emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        #         check.component("my-id", "host", data)
        #         component = topology.get_snapshot(check.check_id)['components'][0]
        #         # there should be only one identifier mapped for host because only `host` type exist
        #         assert component["data"]["identifiers"] == ["urn:computer:/identifier-url"]
        #
        #     def test_component_with_identifier_mapping_with_existing_identifier(self, topology):
        #         """
        #         Test should generate identifier mapping based on the prefix and field value with extra identifier
        #         """
        #         check = IdentifierMappingTestAgentCheck()
        #         data = {"url": "identifier-url", "identifiers": ["urn:host:/host-1"],
        #                 "nestedobject": {"nestedkey": "nestedValue"}}
        #         check.component("my-id", "host", data)
        #         component = topology.get_snapshot(check.check_id)['components'][0]
        #         # there should be 2 identifier mapped for host because there was an existing identifier
        #         assert component["data"]["identifiers"] == ["urn:host:/host-1", "urn:computer:/identifier-url"]
        #
        #     def test_component_identifier_mapping_with_no_field(self, topology):
        #         """
        #         Test should not generate identifier mapping because field value doesn't exist in data
        #         """
        #         check = IdentifierMappingTestAgentCheck()
        #         data = {"emptykey": None, "nestedobject": {"nestedkey": "nestedValue"}}
        #         check.component("my-id", "host", data)
        #         component = topology.get_snapshot(check.check_id)['components'][0]
        #         # there should be no identifier mapped for host because field value `url` doesn't exist in data
        #         assert component["data"].get("identifiers") is None
        #
        #     def test_component_identifier_mapping_with_nested_field(self, topology):
        #         """
        #         Test should generate identifier mapping because based on the prefix and nested field value
        #         """
        #         check = NestedIdentifierMappingTestAgentCheck()
        #         data = {"emptykey": None, "x": {"y": {"z": {"url": "identifier-url"}}}}
        #         check.component("my-id", "host", data)
        #         component = topology.get_snapshot(check.check_id)['components'][0]
        #         # there should be one identifier mapped for host because only `host` type exist on the nested field
        #         assert component["data"]["identifiers"] == ["urn:computer:/identifier-url"]
        #
        #     def test_component_nested_identifier_mapping_with_no_field(self, topology):
        #         """
        #         Test should not generate identifier mapping because nested field value doesn't exist in data
        #         """
        #         check = NestedIdentifierMappingTestAgentCheck()
        #         data = {"emptykey": None}
        #         check.component("my-id", "host", data)
        #         component = topology.get_snapshot(check.check_id)['components'][0]
        #         # there should be no identifier mapped for host because field value `x.y.z.url` doesn't exist in data
        #         assert component["data"].get("identifiers") is None
        #
        #
        # class TestHealthStreamUrn:
        #     def test_health_stream_urn_escaping(self):
        #         urn = HealthStreamUrn("source.", "stream_id:")
        #         assert urn.urn_string() == "urn:health:source.:stream_id%3A"
        #
        #     def test_verify_types(self):
        #         with pytest.raises(ConversionError) as e:
        #             HealthStreamUrn(None, "stream_id")
        #         assert e.value[0] == "This field is required."
        #
        #         with pytest.raises(ConversionError) as e2:
        #             HealthStreamUrn("source", None)
        #         assert e2.value[0] == "This field is required."
        #
        #
        # class TestHealthStream:
        #     def test_throws_error_when_expiry_on_sub_stream(self):
        #         with pytest.raises(ValueError) as e:
        #             HealthStream(HealthStreamUrn("source.", "stream_id:"), "sub_stream", expiry_seconds=0)
        #         assert str(e.value) == "Expiry cannot be disabled if a substream is specified"
        #
        #     def test_verify_types(self):
        #         with pytest.raises(ValidationError) as e:
        #             HealthStream("str")
        #         assert e.value[0] == "Value must be of class: <class 'stackstate_checks.base.utils.health_api.HealthStreamUrn'>"
        #
        #         with pytest.raises(ValidationError) as e:
        #             HealthStream(HealthStreamUrn("source", "urn"), sub_stream=1)
        #         assert e.value[0] == """Value must be a string"""
        #
        #         with pytest.raises(ConversionError) as e:
        #             HealthStream(HealthStreamUrn("source", "urn"), repeat_interval_seconds="")
        #         assert e.value[0].summary == "Value '' is not int."
        #
        #         with pytest.raises(ConversionError) as e:
        #             HealthStream(HealthStreamUrn("source", "urn"), expiry_seconds="")
        #         assert e.value[0].summary == "Value '' is not int."
        #
        #
        # class TestHealth:
        #     def test_check_state_max_values(self, health):
        #         # Max values: fill in as much of the optional fields as possible
        #         check = HealthCheck()
        #         check._init_health_api()
        #         check.health.check_state("check_id", "name", Health.CRITICAL, "identifier", "message")
        #         health.assert_snapshot(check.check_id, check.get_health_stream(None), check_states=[{
        #             'checkStateId': 'check_id',
        #             'health': 'CRITICAL',
        #             'message': 'message',
        #             'name': 'name',
        #             'topologyElementIdentifier': 'identifier'
        #         }])
        #
        #     def test_check_state_min_values(self, health):
        #         # Min values: fill in as few of the optional fields as possible
        #         check = HealthCheck()
        #         check._init_health_api()
        #         check.health.check_state("check_id", "name", Health.CRITICAL, "identifier")
        #         health.assert_snapshot(check.check_id, check.get_health_stream(None), check_states=[{
        #             'checkStateId': 'check_id',
        #             'health': 'CRITICAL',
        #             'name': 'name',
        #             'topologyElementIdentifier': 'identifier'
        #         }])
        #
        #     def test_check_state_verify_types(self):
        #         check = HealthCheck()
        #         check._init_health_api()
        #         with pytest.raises(DataError):
        #             check.health.check_state(1, "name", Health.CRITICAL, "identifier")
        #
        #         with pytest.raises(DataError):
        #             check.health.check_state("check_id", 1, Health.CRITICAL, "identifier")
        #
        #         with pytest.raises(ValueError):
        #             check.health.check_state("check_id", "name", "bla", "identifier")
        #
        #         with pytest.raises(DataError):
        #             check.health.check_state("check_id", "name", Health.CRITICAL, 1)
        #
        #         with pytest.raises(DataError):
        #             check.health.check_state("check_id", "name", Health.CRITICAL, "identifier", 1)
        #
        #     def test_start_snapshot(self, health):
        #         check = HealthCheck()
        #         check._init_health_api()
        #         check.health.start_snapshot()
        #         health.assert_snapshot(check.check_id,
        #                                check.get_health_stream(None),
        #                                start_snapshot={'expiry_interval_s': 60, 'repeat_interval_s': 15},
        #                                stop_snapshot=None)
        #
        #     def test_start_snapshot_main_stream(self, health):
        #         check = HealthCheckMainStream()
        #         check._init_health_api()
        #         check.health.start_snapshot()
        #         health.assert_snapshot(check.check_id,
        #                                check.get_health_stream(None),
        #                                start_snapshot={'expiry_interval_s': 0, 'repeat_interval_s': 15},
        #                                stop_snapshot=None)
        #
        #     def test_stop_snapshot(self, health):
        #         check = HealthCheck()
        #         check._init_health_api()
        #         check.health.stop_snapshot()
        #         health.assert_snapshot(check.check_id,
        #                                check.get_health_stream(None),
        #                                start_snapshot=None,
        #                                stop_snapshot={})
        #
        #     def test_run_initializes_health_api(self, health):
        #         check = HealthCheck()
        #         check.run()
        #         assert check.health is not None
        #
        #     def test_run_not_initializes_health_api(self, health):
        #         check = HealthCheck(stream=None)
        #         check.run()
        #         assert check.health is None
        #
        #     def test_explicit_collection_interval(self, health):
        #         check = HealthCheck(instance={'collection_interval': 30})
        #         check._init_health_api()
        #         check.health.start_snapshot()
        #         health.assert_snapshot(check.check_id,
        #                                check.get_health_stream(None),
        #                                start_snapshot={'expiry_interval_s': 120, 'repeat_interval_s': 30},
        #                                stop_snapshot=None)
