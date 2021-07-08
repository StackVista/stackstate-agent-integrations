from stackstate_checks.base.stubs import topology as top
from .conftest import BaseApiTest, set_cloudtrail_event


class TestEcs(BaseApiTest):
    def get_api(self):
        return "ecs"

    def test_process_ecs(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]
        # default cluster
        comp = top.assert_component(
            components,
            "arn:aws:ecs:eu-west-1:731070500579:cluster/default",
            "aws.ecs.cluster",
            checks={
                "Name": "default",
                "Tags.stackstate-identifier": "sts-ecs-test",
                "CW.Dimensions": [{"Key": "ClusterName", "Value": "default"}],
            },
        )
        self.assert_location_info(comp)
        # ECS Cluster
        top.assert_component(
            components,
            "arn:aws:ecs:eu-west-1:731070500579:cluster/StackState-ECS-Cluster",
            "aws.ecs.cluster",
            checks={
                "Name": "StackState-ECS-Cluster",
                "Tags.StackstateIdentifier": "camel-case-id",
                "CW.Dimensions": [{"Key": "ClusterName", "Value": "StackState-ECS-Cluster"}],
            },
        )
        # service
        top.assert_component(
            components,
            "arn:aws:ecs:eu-west-1:731070500579:service/sample-app-service",
            "aws.ecs.service",
            checks={
                "Name": "sample-app-service",
                "CW.Dimensions": [
                    {"Key": "ClusterName", "Value": "default"},
                    {"Key": "ServiceName", "Value": "sample-app-service"},
                ],
                "URN": [
                    "urn:service:/service-sample-app-service-sample-app",
                    "urn:service:/service-sample-app-service-xray-daemon",
                ],
            },
        )
        # task
        top.assert_component(
            components,
            "arn:aws:ecs:eu-west-1:731070500579:task/f89e69d0-0829-48b8-a503-c7b02a62fe9f",
            "aws.ecs.task",
            checks={
                "Name": "first-run-task-definition:2",
                "URN": [
                    "urn:service-instance:/service-sample-app-service-sample-app:/10.0.0.53",
                    "urn:service-instance:/service-sample-app-service-xray-daemon:/10.0.0.54",
                ],
            },
        )
        # default cluster has a service
        top.assert_relation(
            relations,
            "arn:aws:ecs:eu-west-1:731070500579:cluster/default",
            "arn:aws:ecs:eu-west-1:731070500579:service/sample-app-service",
            "has_cluster_node",
        )
        # service has a task
        top.assert_relation(
            relations,
            "arn:aws:ecs:eu-west-1:731070500579:service/sample-app-service",
            "arn:aws:ecs:eu-west-1:731070500579:task/f89e69d0-0829-48b8-a503-c7b02a62fe9f",
            "has_cluster_node",
        )
        # service has a lb targetgroup
        top.assert_relation(
            relations,
            "arn:aws:ecs:eu-west-1:731070500579:service/sample-app-service",
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/EC2Co-Defau-7HYSTVRX07KO/a7e4eb718fda7510",
            "uses-service",
        )
        # ECS cluster has an instance
        top.assert_relation(
            relations, "arn:aws:ecs:eu-west-1:731070500579:cluster/StackState-ECS-Cluster", "string", "uses-ec2-host"
        )
        top.assert_all_checked(components, relations)

    @set_cloudtrail_event("create_cluster")
    def test_process_ecs_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertGreater(len(topology[0]["components"]), 0)
        top.assert_component(
            topology[0]["components"], "arn:aws:ecs:eu-west-1:731070500579:cluster/default", "aws.ecs.cluster"
        )

    @set_cloudtrail_event("create_service")
    def test_process_ecs_create_service(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertGreater(len(topology[0]["components"]), 0)
        top.assert_component(
            topology[0]["components"], "arn:aws:ecs:eu-west-1:731070500579:cluster/default", "aws.ecs.cluster"
        )
