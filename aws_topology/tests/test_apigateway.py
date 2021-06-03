from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest


class TestApiGateway(BaseApiTest):

    def get_api(self):
        return "apigateway"

    def get_account_id(self):
        return "731070500579"

    def test_process_apigateway(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        api_arn = "arn:aws:execute-api:eu-west-1:731070500579:api_1"
        stage_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}"
        resource_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/*/hello"
        method_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/{}/hello"
        lambda_arn_prefix = "arn:aws:lambda:eu-west-1:731070500579:function:{}"
        sqs_arn = "arn:aws:sqs:eu-west-1:508573134510:STS_stackpack_test"

        # we have 2 stages
        for n in range(0, 2):
            # each state has 1 stage + 5 methods + 1 resource + 1 integration = 8*2 = 16 components
            # stage
            self.assert_has_component(
                components,
                stage_arn_prefix.format(n + 1),
                "aws.apigateway.stage",
                checks={
                    "RestApiName": "api_1",
                    "Tags.StageTagKey"+str(n+1): "StageTagValue"+str(n+1),
                    "CW.Dimensions": [
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )
            # resource
            self.assert_has_component(
                components,
                resource_arn_prefix.format(n + 1),
                "aws.apigateway.resource",
                checks={
                    "Path": "/hello",
                    "CW.Dimensions": [
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

            self.assert_has_component(
                components,
                method_arn_prefix.format(n + 1, "DELETE"),
                "aws.apigateway.method",
                checks={
                    "HttpMethod": "DELETE",
                    "CW.Dimensions": [
                        {"Key": "Method", "Value": "DELETE"},
                        {"Key": "Resource", "Value": "/hello"},
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

            self.assert_has_component(
                components,
                method_arn_prefix.format(n + 1, "GET"),
                "aws.apigateway.method",
                checks={
                    "HttpMethod": "GET",
                    "CW.Dimensions": [
                        {"Key": "Method", "Value": "GET"},
                        {"Key": "Resource", "Value": "/hello"},
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

            self.assert_has_component(
                components,
                method_arn_prefix.format(n + 1, "PATCH"),
                "aws.apigateway.method",
                checks={
                    "HttpMethod": "PATCH",
                    "CW.Dimensions": [
                        {"Key": "Method", "Value": "PATCH"},
                        {"Key": "Resource", "Value": "/hello"},
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

            self.assert_has_component(
                components,
                method_arn_prefix.format(n + 1, "POST"),
                "aws.apigateway.method",
                checks={
                    "HttpMethod": "POST",
                    "CW.Dimensions": [
                        {"Key": "Method", "Value": "POST"},
                        {"Key": "Resource", "Value": "/hello"},
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

            self.assert_has_component(
                components,
                "urn:service:/84.35.236.89",
                "aws.apigateway.method.http.integration"
            )

            self.assert_has_component(
                components,
                method_arn_prefix.format(n + 1, "PUT"),
                "aws.apigateway.method",
                checks={
                    "HttpMethod": "PUT",
                    "CW.Dimensions": [
                        {"Key": "Method", "Value": "PUT"},
                        {"Key": "Resource", "Value": "/hello"},
                        {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                        {"Key": "ApiName", "Value": "api_1"}
                    ]
                }
            )

        self.assert_has_component(
            components,
            api_arn,
            "aws.apigateway"
        )

        # we have 2 stages
        relations = topology[0]["relations"]
        for n in range(1, 3):
            self.assert_has_relation(
                relations, api_arn, stage_arn_prefix.format(n)
            )

            self.assert_has_relation(
                relations, stage_arn_prefix.format(n), resource_arn_prefix.format(n)
            )

            self.assert_has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "PATCH")
            )
            self.assert_has_relation(
                relations, method_arn_prefix.format(n, "PATCH"), sqs_arn
            )

            self.assert_has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "PUT")
            )
            self.assert_has_relation(
                relations, method_arn_prefix.format(n, "PUT"), lambda_arn_prefix.format("PutHello-1LUD3ESBOR6EY")
            )

            self.assert_has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "POST")
            )
            self.assert_has_relation(
                relations, method_arn_prefix.format(n, "POST"), "urn:service:/84.35.236.89"
            )

            self.assert_has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "GET")
            )
            self.assert_has_relation(
                relations, method_arn_prefix.format(n, "GET"), lambda_arn_prefix.format("GetHello-1CZ5O92284Z69")
            )

            self.assert_has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "DELETE")
            )
            self.assert_has_relation(
                relations, method_arn_prefix.format(n, "DELETE"), lambda_arn_prefix.format("DeleteHello-1LDFJCU54ZL5")
            )

        self.assertEqual(len(components), self.components_checked)
        self.assertEqual(len(relations), self.relations_checked)
