from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestLambda(BaseApiTest):
    def get_api(self):
        return "lambda"

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return "eu-west-1"

    def test_process_lambda(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]
        # Function
        comp = top.assert_component(
            components,
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            "aws.lambda.function",
            checks={"FunctionName": "com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY", "Tags.Group": "StackState"},
        )
        self.assert_location_info(comp)
        # lambda sts-xray-test-01
        top.assert_component(
            components, "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-01", "aws.lambda.function"
        )
        # Lambda sts-xray-test-01 has an alias
        top.assert_component(
            components,
            "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-01:old",
            "aws.lambda.alias",
            checks={"Function.FunctionName": "sts-xray-test-01", "Name": "old"},
        )
        # sts-xray-test-01 has vpcid
        top.assert_relation(
            relations, "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-01", "vpc-c6d073bf", "uses-service"
        )
        # alias also has relation with vpcid
        top.assert_relation(
            relations,
            "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-01:old",
            "vpc-c6d073bf",
            "uses-service",
        )

        top.assert_component(
            components, "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-02", "aws.lambda.function"
        )
        # Lambda sts-xray-test-02 has an alias
        top.assert_component(
            components,
            "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-02:altnm",
            "aws.lambda.alias",
            checks={"Function.FunctionName": "sts-xray-test-02", "Name": "altnm"},
        )

        top.assert_relation(
            relations,
            "arn:aws:lambda:eu-west-1:731070500579:function:sts-xray-test-02",
            "arn:aws:rds:eu-west-1:731070500579:db:sn1e7g5j33vyr4o",
            "uses-service",
        )
        top.assert_relation(
            relations,
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-PersonIdDynamoDBHandler-6KMIBXKKKCEZ",
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
            "uses-service",
        )
        top.assert_relation(
            relations,
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-PersonCreatedKinesisHand-19T8EJADX2DE",
            "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1",
            "uses-service",
        )

        # sqs relation goes in different direction hence source and target are not like in other asserts
        top.assert_relation(
            relations,
            'arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test',
            'arn:aws:lambda:eu-west-1:714565590525:function:StackState-Publisher',
            'uses-service'
        )
        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("create_function")
    def test_process_lambda_create_function(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            topology[0]["components"][0]["id"],
        )

    @set_cloudtrail_event("delete_function")
    def test_process_lambda_delete_function(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn("arn:aws:lambda:eu-west-1:731070500579:function:JpkTest", self.check.delete_ids)
        topology = top.get_snapshot(self.check.check_id)
        assert topology["delete_ids"] == ["arn:aws:lambda:eu-west-1:731070500579:function:JpkTest"]

    @set_cloudtrail_event("update_function")
    def test_process_lambda_update_function(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            topology[0]["components"][0]["id"],
        )

    @set_cloudtrail_event("publish_version")
    def test_process_lambda_publish_version(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            topology[0]["components"][0]["id"],
        )

    @set_cloudtrail_event("add_permission")
    def test_process_lambda_add_permission(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            topology[0]["components"][0]["id"],
        )

    @set_cloudtrail_event("tag_function")
    def test_process_lambda_tag_function(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_updated_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            topology[0]["components"][0]["id"],
        )
