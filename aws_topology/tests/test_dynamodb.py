from stackstate_checks.aws_topology.resources.utils import deep_sort_lists
from stackstate_checks.base.stubs import topology as top, aggregator
from .conftest import BaseApiTest, set_cloudtrail_event


class TestDynamoDB(BaseApiTest):

    def get_api(self):
        return "dynamodb"

    def get_account_id(self):
        return "731070500579"
    
    def get_region(self):
        return 'eu-west-1'

    def test_process_dynamodb(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        # table_1
        self.assert_has_component(
            components,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1",
            "aws.dynamodb",
            checks={
                "TableArn": "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1",
                "Name": "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1",
                "CW.Dimensions": [{"Key": "TableName", "Value": "table_1"}]
            }
        )
        # table_1.stream
        self.assert_has_component(
            components,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
            "aws.dynamodb.streams",
            checks={
                "LatestStreamArn": "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
                "Name": "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
                "CW.Dimensions": [
                    {"Key": "TableName", "Value": "table_1"},
                    {"Key": "StreamLabel", "Value": "2018-05-17T08:09:27.110"}
                ]
            }
        )
        # table_1 <-> stream
        self.assert_has_relation(
            relations,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1",
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110"
        )

        self.assert_has_component(
            components,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_2",
            "aws.dynamodb"
        )
        self.assert_has_component(
            components,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_3",
            "aws.dynamodb"
        )
        self.assert_has_component(
            components,
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_4",
            "aws.dynamodb"
        )
     
        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)


    @set_cloudtrail_event('create_table')
    def test_process_dynamodb_create_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_2',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_cloudtrail_event('delete_table')
    def test_process_dynamodb_delete_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:dynamodb:eu-west-1:731070500579:table/table_2', self.check.delete_ids)

    @set_cloudtrail_event('tag_table')
    def test_process_dynamodb_tag_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_2',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_cloudtrail_event('untag_table')
    def test_process_dynamodb_untag_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_2',
            topology[0]["components"][0]["data"]["Name"]
        )
