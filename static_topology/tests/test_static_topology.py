# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# 3p
import mock
import unittest
import pytest

from stackstate_checks.base import ConfigurationError, AgentIntegrationTestUtil
from stackstate_checks.static_topology import StaticTopologyCheck
from stackstate_checks.base.stubs import topology, aggregator


class MockFileReader:
    """used to mock codec.open, it returns content for a with-construct."""

    def __init__(self, location, content):
        """
        :param location: the csv file location, used to return value of content[location]
        :param content: dict(key: location, value: array of to delimit strings)
        """
        self.content = content
        self.location = location

    def __enter__(self):
        return self.content[self.location]

    def __exit__(self, type, value, traceback):
        pass


@pytest.mark.usefixtures("instance")
class TestStaticCSVTopology(unittest.TestCase):
    """
    Unit tests for Static Topology AgentCheck.
    """
    CHECK_NAME = "static_topology"

    config = {
        'init_config': {},
        'instances': [
            {
                'type': 'csv',
                'components_file': '/dev/null',
                'relations_file': '/dev/null',
                'delimiter': ';'
            }
        ]
    }

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        # Initialize
        config = {}
        self.check = StaticTopologyCheck(self.CHECK_NAME, config, instances=[self.instance])

    def test_omitted_component_file(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'delimiter': ';'
                }
            ]
        }
        with self.assertRaises(ConfigurationError) as context:
            self.check.check(config["instances"][0])
        self.assertTrue('Static topology instance missing "components_file" value.' in str(context.exception))

    def test_omitted_relation_file(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'components_file': '/dev/null',
                    'delimiter': ';'
                }
            ]
        }
        with self.assertRaises(ConfigurationError) as context:
            self.check.check(config["instances"][0])
        self.assertTrue('Static topology instance missing "relations_file" value.' in str(context.exception))

    def test_empty_component_file(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'components_file': '/dev/null',
                    'relations_file': '/dev/null',
                    'delimiter': ';'
                }
            ]
        }

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.check(config["instances"][0])
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "Component CSV file is empty.")

    def test_empty_relation_file(self):
        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'components_file': '/ignored/',
                    'relations_file': '/dev/null',
                    'delimiter': ';'
                }
            ]
        }

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.check(config["instances"][0])
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type', '1,name1,type1', '2,name2,type2'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        topo_instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, topo_instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, topo_instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, topo_instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, topo_instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, topo_instances['relations'][1])
        self.assertEqual(len(topo_instances['components']), 5)
        self.assertEqual(len(topo_instances['relations']), 3)

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type', '1,name1,type1', '2,name2,type2'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_snapshot(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        self.assertTrue(instances['start_snapshot'], msg='start_snapshot was not set to True')
        self.assertTrue(instances['stop_snapshot'], msg='stop_snapshot was not set to True')

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type', '1,name1,type1', '2,name2,type2'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_instance_tags(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'components_file': 'component.csv',
                    'relations_file': 'relation.csv',
                    'delimiter': ',',
                    'tags': ['tag1', 'tag2']
                }
            ]
        }
        self.check.check(config["instances"][0])
        instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(instances['components']), 2)
        self.assertEqual(len(instances['components'][0]['data']['labels']), 4)
        self.assertEqual(len(instances['components'][1]['data']['labels']), 4)
        self.assertIn("csv.component:component.csv", instances['components'][0]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][0]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][1]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][1]['data']['labels'])

        self.assertEqual(len(instances['relations']), 1)
        self.assertNotIn('labels', instances['relations'][0]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,labels', '1,name1,type1,label1', '2,name2,type2,'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_labels(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['labels']), 3)
        self.assertEqual(len(instances['components'][4]['data']['labels']), 2)
        self.assertIn("csv.component:component.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][4]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][4]['data']['labels'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,labels', '1,name1,type1,"label1,label2"',
                                      '2,name2,type2,"label1,label2,label3"'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_multiple_labels(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['labels']), 4)
        self.assertEqual(len(instances['components'][4]['data']['labels']), 5)
        self.assertIn("label1", instances['components'][3]['data']['labels'])
        self.assertIn("label2", instances['components'][3]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][3]['data']['labels'])
        self.assertIn("label1", instances['components'][4]['data']['labels'])
        self.assertIn("label2", instances['components'][4]['data']['labels'])
        self.assertIn("label3", instances['components'][4]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][4]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][4]['data']['labels'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,identifiers', '1,name1,type1,id1', '2,name2,type2,'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_identifier(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['identifiers']), 1)
        self.assertEqual(len(instances['components'][4]['data']['identifiers']), 0)
        self.assertIn("id1", instances['components'][3]['data']['identifiers'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,identifiers', '1,name1,type1,"id1,id2"',
                                      '2,name2,type2,"id1,id2,id3"'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_multiple_identifiers(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['identifiers']), 2)
        self.assertEqual(len(instances['components'][4]['data']['identifiers']), 3)
        self.assertIn("id1", instances['components'][3]['data']['identifiers'])
        self.assertIn("id2", instances['components'][3]['data']['identifiers'])
        self.assertIn("id1", instances['components'][4]['data']['identifiers'])
        self.assertIn("id2", instances['components'][4]['data']['identifiers'])
        self.assertIn("id3", instances['components'][4]['data']['identifiers'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,labels', '1,name1,type1,label1', '2,name2,type2,'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_labels_and_instance_tags(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        config = {
            'init_config': {},
            'instances': [
                {
                    'type': 'csv',
                    'components_file': 'component.csv',
                    'relations_file': 'relation.csv',
                    'delimiter': ',',
                    'tags': ['tag1', 'tag2']
                }
            ]
        }
        self.check.check(config["instances"][0])
        instances = topology.get_snapshot(self.check.check_id)
        self.assertEqual(len(instances['components']), 2)
        self.assertEqual(len(instances['components'][0]['data']['labels']), 5)
        self.assertEqual(len(instances['components'][1]['data']['labels']), 4)
        self.assertIn("csv.component:component.csv", instances['components'][0]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][0]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][1]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][1]['data']['labels'])

        self.assertEqual(len(instances['relations']), 1)
        self.assertNotIn('labels', instances['relations'][0]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,environments', '1,name1,type1,env1', '2,name2,type2,'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_environments(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['labels']), 2)
        self.assertEqual(len(instances['components'][4]['data']['labels']), 2)
        self.assertIn("csv.component:component.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.component:component.csv", instances['components'][4]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][4]['data']['labels'])
        self.assertEqual(len(instances['components'][3]['data']['environments']), 1)
        self.assertEqual(len(instances['components'][4]['data']['environments']), 1)
        self.assertIn("env1", instances['components'][3]['data']['environments'])
        self.assertIn("Production", instances['components'][4]['data']['environments'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open',
                side_effect=lambda location, mode, encoding: MockFileReader(location, {
                    'component.csv': ['id,name,type,environments', '1,name1,type1,"env1,env2"', '2,name2,type2,'],
                    'relation.csv': ['sourceid,targetid,type', '1,2,type']}))
    def test_topology_with_multiple_environments(self, mock):

        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['components'][3]['data']['labels']), 2)
        self.assertEqual(len(instances['components'][4]['data']['labels']), 2)
        self.assertIn("csv.component:component.csv", instances['components'][3]['data']['labels'])
        self.assertIn("csv.relation:relation.csv", instances['components'][4]['data']['labels'])
        self.assertEqual(len(instances['components'][3]['data']['environments']), 2)
        self.assertEqual(len(instances['components'][4]['data']['environments']), 1)
        self.assertIn("env1", instances['components'][3]['data']['environments'])
        self.assertIn("env2", instances['components'][3]['data']['environments'])
        self.assertIn("Production", instances['components'][4]['data']['environments'])

        self.assertEqual(len(instances['relations']), 3)
        self.assertNotIn('labels', instances['relations'][2]['data'])

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['NOID,name,type'],
        'relation.csv': []}))
    def test_missing_component_id_field(self, mock):

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header id not found in component csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,NONAME,type'],
        'relation.csv': []}))
    def test_missing_component_name_field(self, mock):

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header name not found in component csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,NOTYPE'],
        'relation.csv': []}))
    def test_missing_component_type_field(self, mock):

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header type not found in component csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type', 'id1,name1,type1', ''],
        'relation.csv': ['sourceid,targetid,type']}))
    def test_handle_empty_component_line(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 4)
        self.assertEqual(len(instances['relations']), 2)

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type,othervalue', 'id1,name1,type1,othervalue', 'id2,name2,type2'],
        'relation.csv': ['sourceid,targetid,type']}))
    def test_handle_incomplete_component_line(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 4)
        self.assertEqual(len(instances['relations']), 2)

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type'],
        'relation.csv': ['NOSOURCEID,targetid,type']}))
    def test_missing_relation_sourceid_field(self, mock):

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header sourceid not found in relation csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type'],
        'relation.csv': ['sourceid,NOTARGETID,type']}))
    def test_missing_relation_targetid_field(self, mock):

        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header targetid not found in relation csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type'],
        'relation.csv': ['sourceid,targetid,NOTYPE']}))
    def test_missing_relation_type_field(self, mock):
        # TODO this is needed because the topology retains data across tests
        aggregator.reset()

        self.check.run()
        service_checks = aggregator.service_checks("StaticTopology")
        self.assertEqual(service_checks[0].status, 2)
        self.assertEqual(service_checks[0].message, "CSV header type not found in relation csv.")

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type', 'id1,name1,type1', 'id2,name2,type2'],
        'relation.csv': ['sourceid,targetid,type', 'id1,id2,uses', '']}))
    def test_handle_empty_relation_line(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['relations']), 3)

    @mock.patch('codecs.open', side_effect=lambda location, mode, encoding: MockFileReader(location, {
        'component.csv': ['id,name,type', 'id1,name1,type1', 'id2,name2,type2'],
        'relation.csv': ['sourceid,targetid,type,othervalue', 'id1,id2,uses,othervalue', 'id2,id3,uses']}))
    def test_handle_incomplete_relation_line(self, mock):
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check.run()
        instances = topology.get_snapshot(self.check.check_id)
        AgentIntegrationTestUtil.assert_agent_component(self, instances['components'][0])
        AgentIntegrationTestUtil.assert_agent_integration_component(self, instances['components'][1])
        AgentIntegrationTestUtil.assert_agent_integration_instance_component(self, instances['components'][2])
        AgentIntegrationTestUtil.assert_agent_integration_relation(self, instances['relations'][0])
        AgentIntegrationTestUtil.assert_agent_integration_instance_relation(self, instances['relations'][1])
        self.assertEqual(len(instances['components']), 5)
        self.assertEqual(len(instances['relations']), 3)
