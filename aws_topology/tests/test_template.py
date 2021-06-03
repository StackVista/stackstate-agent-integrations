import difflib
import unittest
import os
import json
from mock import patch
import dateutil.parser
import datetime
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology.resources import ResourceRegistry
from botocore.exceptions import ClientError
from copy import deepcopy
import traceback
from parameterized import parameterized
import sys
import pytest

requires_py3 = pytest.mark.skipif(
    sys.version_info.major < 3, reason="Only python3 because of type hinting"
)


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path("json/template/" + path)) as f:
        x = json.load(f)
    return x


def normalize_relation(r):
    r["source_id"] = r.pop("sourceId")
    r["target_id"] = r.pop("targetId")
    r.pop("externalId")
    r["type"] = r["type"]["name"]

    return r


def normalize_component(r):
    r["id"] = r.pop("externalId")
    r["type"] = r["type"]["name"]
    return r


TEST_REGION = "eu-west-1"
THROTTLING_COUNT_TAGS = 0


def set_api(value):
    def inner(func):
        func.api = value
        return func

    return inner


original = ResourceRegistry.get_registry


def get_wrapper(check_name):

    def registry_wrapper():
        # get the original registry
        registry = deepcopy(original())
        parts = check_name.split("|", 1)
        comptype = None
        api = parts[0]
        if len(parts) > 1:
            comptype = parts[1]

        api_type = 'global' if api.startswith('route53') else 'regional'

        orig = registry[api_type][api]

        # error class
        class error(object):
            API = "error"
            MEMORY_KEY = None

            def __init__(self, location_info, client, agent):
                self.original_processor = orig(location_info, client, agent)

            def get_delete_ids(self):
                return []

            def process_all(self, filter=None):
                if comptype is None:
                    raise Exception("Oops")
                else:
                    return self.original_processor.process_all(filter=comptype)

        registry[api_type][api] = error
        return registry
    return registry_wrapper


def dont_send_parked_relations(self):
    pass


def mock_boto_calls(self, operation_name, kwarg):
    # print(operation_name)
    if operation_name == "AssumeRole":
        return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
    elif operation_name == "DescribeInstances":
        test_event = resource("test_describe_ec2.json")
        for reservation in test_event["Reservations"]:
            for instance_data in reservation["Instances"]:
                instance_data["LaunchTime"] = dateutil.parser.parse(instance_data["LaunchTime"])
                for network_interface in instance_data["NetworkInterfaces"]:
                    network_interface["Attachment"]["AttachTime"] = dateutil.parser.parse(
                        network_interface["Attachment"]["AttachTime"]
                    )
                for block_device_mappings in instance_data["BlockDeviceMappings"]:
                    block_device_mappings["Ebs"]["AttachTime"] = dateutil.parser.parse(
                        block_device_mappings["Ebs"]["AttachTime"]
                    )

        return test_event
    elif operation_name == "DescribeSecurityGroups":
        return resource("test_describe_security_groups.json")

    elif operation_name == "DescribeInstanceTypes":
        return resource("test_describe_instance_types.json")

    elif operation_name == "GetCallerIdentity":
        return resource("test_get_caller_identity.json")

    elif operation_name == "DescribeStacks":
        return resource("test_describe_cloudformation_stacks.json")

    elif operation_name == "DescribeStackResources":
        return resource("test_describe_cloudformation_stack_resources.json")

    elif operation_name == "ListStacks":
        return resource("test_cloudformation_list_stacks.json")

    elif operation_name == "DescribeInstanceHealth":
        return resource("test_describe_instance_health.json")

    elif operation_name == "DescribeLoadBalancers":
        if self._service_model.service_name == "elb":
            if operation_name == "DescribeLoadBalancers":
                test_event = resource("test_describe_load_balancers_classic.json")
                for load_balancers in test_event["LoadBalancerDescriptions"]:
                    load_balancers["CreatedTime"] = dateutil.parser.parse(load_balancers["CreatedTime"])

                return test_event

            else:
                raise ValueError("Unknown operation name", operation_name)

        else:
            test_event = resource("test_describe_load_balancers.json")
            for load_balancer in test_event["LoadBalancers"]:
                load_balancer["CreatedTime"] = dateutil.parser.parse(load_balancer["CreatedTime"])

            return test_event

    elif operation_name == "DescribeListeners":
        return resource("test_describe_listeners.json")

    elif operation_name == "DescribeTargetGroups":
        return resource("test_describe_target_groups.json")

    elif operation_name == "DescribeTargetHealth":
        return resource("test_decribe_target_health.json")

    elif operation_name == "ListBuckets":
        test_event = resource("test_describe_s3.json")
        for bucket in test_event["Buckets"]:
            bucket["CreationDate"] = dateutil.parser.parse(bucket["CreationDate"])
        return test_event

    elif operation_name == "DescribeDBInstances":
        test_event = resource("test_describe_rds_instances.json")
        for instance in test_event["DBInstances"]:
            instance["InstanceCreateTime"] = dateutil.parser.parse(instance["InstanceCreateTime"])
        return test_event

    elif operation_name == "DescribeDBClusters":
        test_event = resource("test_describe_rds_clusters.json")
        for cluster in test_event["DBClusters"]:
            cluster["LatestRestorableTime"] = dateutil.parser.parse(cluster["LatestRestorableTime"])
            cluster["EarliestRestorableTime"] = dateutil.parser.parse(cluster["EarliestRestorableTime"])
            cluster["ClusterCreateTime"] = dateutil.parser.parse(cluster["ClusterCreateTime"])
        return test_event

    elif operation_name == "ListFunctions":
        test_event = resource("test_lambda_list_functions.json")
        for fn in test_event["Functions"]:
            fn["LastModified"] = dateutil.parser.parse(fn["LastModified"])
        return test_event

    elif operation_name == "ListEventSourceMappings":
        document = resource("test_lambda_list_event_source_mappings.json")
        for mapping in document["EventSourceMappings"]:
            mapping["LastModified"] = datetime.datetime.fromtimestamp(mapping["LastModified"])
        return document

    elif operation_name == "ListTopics":
        return resource("test_sns_list_topics.json")

    elif operation_name == "ListQueues":
        return resource("test_sqs_list_queues.json")

    elif operation_name == "GetQueueAttributes":
        return resource("test_sqs_get_queue_attributes.json")

    elif operation_name == "ListQueueTags":
        return resource("test_sqs_list_queue_tags.json")

    elif operation_name == "GetQueueUrl":
        return resource("test_sqs_get_queue_url.json")

    elif operation_name == "ListMetrics":
        return resource("test_cw_list_metrics.json")

    elif operation_name == "ListSubscriptionsByTopic":
        return resource("test_sns_list_subscriptions_by_topic.json")

    elif operation_name == "GetBucketNotificationConfiguration":
        return resource("test_s3_get_bucket_notification_configuration.json")

    elif operation_name == "ListTables":
        return resource("test_dynamodb_list_tables.json")

    elif operation_name == "ListTags":
        global THROTTLING_COUNT_TAGS
        if THROTTLING_COUNT_TAGS < 50:
            THROTTLING_COUNT_TAGS += 1
            error_response = {"Error": {"Code": "RequestLimitExceeded", "Message": "Maximum sending rate exceeded"}}
            raise ClientError(error_response, operation_name)
        else:
            return resource("test_lambda_list_tags.json")

    elif operation_name == "ListAliases":
        return resource("test_lambda_list_aliases.json")

    elif operation_name == "DescribeTable":
        path_name = "test_dynamodb_describe_table_" + kwarg["TableName"] + ".json"
        document = resource(path_name)
        document["Table"]["CreationDateTime"] = datetime.datetime.fromtimestamp(
            document["Table"]["CreationDateTime"]
        )
        return document

    elif operation_name == "ListStreams":
        return resource("test_kinesis_list_streams.json")

    elif operation_name == "DescribeStreamSummary":
        path_name = "test_kinesis_describe_stream_summary_" + kwarg["StreamName"] + ".json"
        document = resource(path_name)
        document["StreamDescriptionSummary"]["StreamCreationTimestamp"] = datetime.datetime.fromtimestamp(
            document["StreamDescriptionSummary"]["StreamCreationTimestamp"]
        )
        return document

    elif operation_name == "ListDeliveryStreams":
        return resource("test_firehose_list_delivery_streams.json")

    elif operation_name == "DescribeDeliveryStream":
        path_name = "test_firehose_describe_delivery_stream_" + kwarg["DeliveryStreamName"] + ".json"
        document = resource(path_name)
        document["DeliveryStreamDescription"]["CreateTimestamp"] = datetime.datetime.fromtimestamp(
            document["DeliveryStreamDescription"]["CreateTimestamp"]
        )
        if document["DeliveryStreamDescription"].get("Source"):
            if document["DeliveryStreamDescription"]["Source"].get("KinesisStreamSourceDescription"):
                document["DeliveryStreamDescription"]["Source"]["KinesisStreamSourceDescription"][
                    "DeliveryStartTimestamp"
                ] = datetime.datetime.fromtimestamp(
                    document["DeliveryStreamDescription"]["Source"]["KinesisStreamSourceDescription"][
                        "DeliveryStartTimestamp"
                    ]
                )
        return document

    elif operation_name == "GetRestApis":
        return resource("test_apigateway_get_rest_apis.json")

    elif operation_name == "GetStages":
        return resource("test_apigateway_get_stages.json")

    elif operation_name == "GetResources":
        path_name = "test_apigateway_get_resources_" + kwarg["restApiId"] + ".json"
        return resource(path_name)

    elif operation_name == "GetMethod":
        path_name = "test_apigateway_get_method_" + kwarg["httpMethod"].lower() + ".json"
        return resource(path_name)

    elif operation_name == "ListDomains":
        document = resource("test_route53domains_list_domains.json")
        for domain in document["Domains"]:
            domain["Expiry"] = datetime.datetime.fromtimestamp(domain["Expiry"])
        return document

    elif operation_name == "ListHostedZones":
        return resource("test_route53_list_hosted_zones.json")

    elif operation_name == "GetHostedZone":
        return resource("test_route53_get_hosted_zone.json")

    elif operation_name == "ListResourceRecordSets":
        return resource("test_route53_list_resource_record_sets.json")

    elif operation_name == "DescribeAutoScalingGroups":
        document = resource("test_autoscaling_describe_auto_scaling_groups.json")
        for auto_scaling_group in document["AutoScalingGroups"]:
            auto_scaling_group["CreatedTime"] = dateutil.parser.parse(auto_scaling_group["CreatedTime"])
        return document

    elif operation_name == "DescribeVpcs":
        return resource("test_ec2_describe_vpcs.json")

    elif operation_name == "DescribeSubnets":
        return resource("test_ec2_describe_subnets.json")

    elif operation_name == "DescribeVpnGateways":
        return resource("test_ec2_describe_vpn_gateways.json")

    elif operation_name == "GetBucketLocation":
        return resource("test_s3_get_bucket_location.json")

    elif operation_name == "ListTagsForStream":
        return resource("test_kinesis_list_tags_for_stream.json")

    elif operation_name == "ListClusters":
        return resource("test_ecs_list_clusters.json")

    elif operation_name == "DescribeClusters":
        # Unfortunately boto3 uses the same operation name for both ECS cluster and Redshift Cluster
        if self._service_model.service_name == "ecs":
            return resource("test_ecs_describe_clusters.json")
        else:
            return resource("test_redshift_describe_clusters.json")

    elif operation_name == "ListServices":
        return resource("test_ecs_list_services.json")

    elif operation_name == "DescribeServices":
        document = resource("test_ecs_describe_services.json")
        for service in document["services"]:
            service["createdAt"] = dateutil.parser.parse(service["createdAt"])

            for deployment in service["deployments"]:
                deployment["createdAt"] = dateutil.parser.parse(deployment["createdAt"])
                deployment["updatedAt"] = dateutil.parser.parse(deployment["updatedAt"])

            for event in service["events"]:
                event["createdAt"] = dateutil.parser.parse(event["createdAt"])
        return document

    elif operation_name == "ListTagsOfResource":
        return resource("test_dynamodb_list_tags_of_resource.json")

    elif operation_name == "ListTasks":
        return resource("test_ecs_list_tasks.json")

    elif operation_name == "DescribeTasks":
        document = resource("test_ecs_describe_tasks.json")

        for task in document["tasks"]:
            task["createdAt"] = dateutil.parser.parse(task["createdAt"])
            task["startedAt"] = dateutil.parser.parse(task["startedAt"])
            task["connectivityAt"] = dateutil.parser.parse(task["connectivityAt"])
            task["pullStartedAt"] = dateutil.parser.parse(task["pullStartedAt"])
            task["pullStoppedAt"] = dateutil.parser.parse(task["pullStoppedAt"])

        return document

    elif operation_name == "ListContainerInstances":
        return resource("test_ecs_list_container_instances.json")

    elif operation_name == "DescribeContainerInstances":
        return resource("test_ecs_describe_container_instances.json")

    elif operation_name == "ListTagsForResource":
        if self._service_model.service_name == "rds":
            return resource("test_rds_list_tags_for_resource.json")
        elif self._service_model.service_name == "route53":
            return resource("test_route53_list_tags_for_resource.json")
        else:
            return resource("test_sns_list_tags_for_resource.json")
    elif operation_name == "DescribeTags":
        return resource("test_elbv2_describe_tags.json")

    elif operation_name == "GetServiceGraph":
        return resource("test_xray_get_service_graph.json")

    elif operation_name == "GetTraceSummaries":
        return resource("test_xray_get_trace_summaries.json")

    elif operation_name == "ListTagsForDomain":
        return resource("test_route53_domain_tags.json")

    elif operation_name == "ListTagsForDeliveryStream":
        return resource("test_firehose_deliverystream_tags.json")
    elif operation_name == "LookupEvents":
        return {}
    elif operation_name == 'ListStateMachines':
        return {}
    elif operation_name == 'ListActivities':
        return {}
    elif operation_name == 'GetBucketTagging':
        return {}
    else:
        raise ValueError("Unknown operation name", operation_name)


def compute_topologies_diff(computed_dict, expected_filepath):
    with open(expected_filepath) as f:
        expected_topology = f.read()
        top = json.loads(expected_topology)
        top["relations"] = list(map(lambda x: normalize_relation(x), top["relations"]))
        top["relations"].sort(key=lambda x: x["source_id"] + "-" + x["type"] + x["target_id"])
        top["components"] = list(map(lambda x: normalize_component(x), top["components"]))
        top["components"].sort(key=lambda x: x["type"] + "-" + x["id"])
        top["start_snapshot"] = True
        top["stop_snapshot"] = True
        top["instance_key"] = top.pop("instance")
        top.pop("delete_ids")

        for comp in computed_dict["components"]:
            comp["data"].pop("tags")
        computed_dict["relations"].sort(key=lambda x: x["source_id"] + "-" + x["type"] + x["target_id"])
        computed_dict["components"].sort(key=lambda x: x["type"] + "-" + x["id"])
        # with open(relative_path('input.json'), 'wt') as f:
        #     f.write(json.dumps(computed_dict, sort_keys=True, default=str, indent=2))
        # with open(relative_path('expected.json'), 'wt') as f:
        #     f.write(json.dumps(top, default=str, indent=2, sort_keys=True))
        topology = json.dumps(computed_dict, default=str, indent=2, sort_keys=True)
        expected_topology = json.dumps(top, default=str, indent=2, sort_keys=True)
        delta = difflib.unified_diff(a=expected_topology.strip().splitlines(), b=topology.strip().splitlines())
        return "".join(delta)


class TestTemplate(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def assert_location_info(self, component):
        self.assertEqual(component["data"]["Location"]["AwsAccount"], "731070500579")

        if component["type"] == "aws.route53.domain":  # DIFF was ['type']['name']
            self.assertEqual(component["data"]["Location"]["AwsRegion"], "us-east-1")
        elif component["type"] == "aws.route53.hostedzone":  # DIFF was ['type']['name']
            self.assertEqual(component["data"]["Location"]["AwsRegion"], "us-east-1")
        else:
            self.assertEqual(component["data"]["Location"]["AwsRegion"], TEST_REGION)

    def assert_stream_dimensions(self, element, dimensions):
        self.assertEqual(element["data"]["CW"]["Dimensions"], dimensions)

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    def unique_topology_types(self, topology):
        return set([c["type"] for ti in topology for c in ti["components"]])  # DIFF

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        """
        method = getattr(self, self._testMethodName)
        self.patcher = patch("botocore.client.BaseClient._make_api_call")
        self.mock_object = self.patcher.start()
        top.reset()
        aggregator.reset()
        init_config = InitConfig({
            "aws_access_key_id": "some_key",
            "aws_secret_access_key": "some_secret",
            "external_id": "disable_external_id_this_is_unsafe"
        })
        instance = {
            "role_arn": "arn:aws:iam::731070500579:role/RoleName",
            "regions": ["global", "eu-west-1"],
        }
        if method.api:
            if method.api.startswith('route53'):
                instance = {
                    "role_arn": "arn:aws:iam::731070500579:role/RoleName",
                    "regions": ["global"],
                }
            else:
                instance = {
                    "role_arn": "arn:aws:iam::731070500579:role/RoleName",
                    "regions": ["eu-west-1"],
                }
            instance.update({"apis_to_run": [method.api]})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = mock_boto_calls

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("dynamodb|aws.dynamodb")
    def test_process_dynamodb(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1"
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][0]["target_id"],
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
        )  # DIFF
        self.assertEqual(len(topology[0]["components"]), 5)
        self.assertEqual(
            topology[0]["components"][0]["id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1"
        )  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["TableArn"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1"
        )
        self.assertEqual(topology[0]["components"][0]["type"], "aws.dynamodb")  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["Name"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1"
        )
        self.assert_stream_dimensions(topology[0]["components"][0], [{"Key": "TableName", "Value": "table_1"}])
        self.assertEqual(
            topology[0]["components"][1]["id"],
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
        )  # DIFF
        self.assertEqual(topology[0]["components"][1]["type"], "aws.dynamodb.streams")  # DIFF
        self.assertEqual(
            topology[0]["components"][1]["data"]["LatestStreamArn"],
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
        )
        self.assertEqual(
            topology[0]["components"][1]["data"]["Name"],
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
        )
        self.assert_stream_dimensions(
            topology[0]["components"][1],
            [{"Key": "TableName", "Value": "table_1"}, {"Key": "StreamLabel", "Value": "2018-05-17T08:09:27.110"}],
        )
        self.assertEqual(
            topology[0]["components"][2]["id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_2"
        )  # DIFF
        self.assertEqual(topology[0]["components"][2]["type"], "aws.dynamodb")  # DIFF
        self.assertEqual(
            topology[0]["components"][3]["id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_3"
        )  # DIFF
        self.assertEqual(topology[0]["components"][3]["type"], "aws.dynamodb")  # DIFF
        self.assertEqual(
            topology[0]["components"][4]["id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_4"
        )  # DIFF
        self.assertEqual(topology[0]["components"][4]["type"], "aws.dynamodb")  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("apigateway|aws.apigateway.stage")
    def test_process_api_gateway(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        api_arn = "arn:aws:execute-api:eu-west-1:731070500579:api_1"
        stage_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}"
        resource_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/*/hello"
        method_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/{}/hello"
        lambda_arn_prefix = "arn:aws:lambda:eu-west-1:731070500579:function:{}"
        sqs_arn = "arn:aws:sqs:eu-west-1:508573134510:STS_stackpack_test"

        self.assertEqual(len(topology), 1)
        # we have 2 stages
        for n in range(0, 2):
            comp = self.assert_has_component(
                topology[0]["components"],
                stage_arn_prefix.format(n + 1),
                "aws.apigateway.stage"
            )
            self.assertEqual(comp["data"]["RestApiName"], "api_1")
            self.assertEqual(
                comp["data"]["Tags"]["StageTagKey" + str(n + 1)], "StageTagValue" + str(n + 1)
            )
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][0 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                resource_arn_prefix.format(n + 1),
                "aws.apigateway.resource"
            )
            self.assertEqual(comp["data"]["Path"], "/hello")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                method_arn_prefix.format(n + 1, "DELETE"),
                "aws.apigateway.method"
            )
            self.assertEqual(comp["data"]["HttpMethod"], "DELETE")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Method", "Value": comp["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": comp["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                method_arn_prefix.format(n + 1, "GET"),
                "aws.apigateway.method"
            )
            self.assertEqual(comp["data"]["HttpMethod"], "GET")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Method", "Value": comp["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": comp["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                method_arn_prefix.format(n + 1, "PATCH"),
                "aws.apigateway.method"
            )
            self.assertEqual(comp["data"]["HttpMethod"], "PATCH")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Method", "Value": comp["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": comp["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                method_arn_prefix.format(n + 1, "POST"),
                "aws.apigateway.method"
            )
            self.assertEqual(comp["data"]["HttpMethod"], "POST")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Method", "Value": comp["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": comp["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                "urn:service:/84.35.236.89",
                "aws.apigateway.method.http.integration"
            )

            comp = self.assert_has_component(
                topology[0]["components"],
                method_arn_prefix.format(n + 1, "PUT"),
                "aws.apigateway.method"
            )
            self.assertEqual(comp["data"]["HttpMethod"], "PUT")
            self.assert_stream_dimensions(
                comp,
                [
                    {"Key": "Method", "Value": comp["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": comp["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": comp["data"]["RestApiName"]},
                ],
            )

        comp = self.assert_has_component(
            topology[0]["components"],
            api_arn,
            "aws.apigateway"
        )

        self.assertEqual(len(topology[0]["components"]), 31)

        # we have 2 stages
        relations = topology[0]["relations"]
        for n in range(1, 3):
            self.assertEqual(self.has_relation(
                relations, api_arn, stage_arn_prefix.format(n)
            ), True)

            self.assertEqual(self.has_relation(
                relations, stage_arn_prefix.format(n), resource_arn_prefix.format(n)
            ), True)

            self.assertEqual(self.has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "PATCH")
            ), True)
            self.assertEqual(self.has_relation(
                relations, method_arn_prefix.format(n, "PATCH"), sqs_arn
            ), True)

            self.assertEqual(self.has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "PUT")
            ), True)
            self.assertEqual(self.has_relation(
                relations, method_arn_prefix.format(n, "PUT"), lambda_arn_prefix.format("PutHello-1LUD3ESBOR6EY")
            ), True)

            self.assertEqual(self.has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "POST")
            ), True)
            self.assertEqual(self.has_relation(
                relations, method_arn_prefix.format(n, "POST"), "urn:service:/84.35.236.89"
            ), True)

            self.assertEqual(self.has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "GET")
            ), True)
            self.assertEqual(self.has_relation(
                relations, method_arn_prefix.format(n, "GET"), lambda_arn_prefix.format("GetHello-1CZ5O92284Z69")
            ), True)

            self.assertEqual(self.has_relation(
                relations, resource_arn_prefix.format(n), method_arn_prefix.format(n, "DELETE")
            ), True)
            self.assertEqual(self.has_relation(
                relations, method_arn_prefix.format(n, "DELETE"), lambda_arn_prefix.format("DeleteHello-1LDFJCU54ZL5")
            ), True)

        self.assertEqual(len(topology[0]["relations"]), 46)

    def has_relation(self, relations, source_id, target_id):
        for relation in relations:
            if relation['source_id'] == source_id and relation['target_id'] == target_id:
                return True
        return False

    def assert_has_component(self, components, id, tp):
        for component in components:
            if component['id'] == id and component['type'] == tp:
                return component
        self.assertFalse(True, "Component not found " + id + " - " + tp)

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("ecs|aws.ecs.cluster")
    def test_process_ecs(self):
        self.check.run()
        self.assert_executed_ok()
        topology = top.get_snapshot(self.check.check_id)

        diff = compute_topologies_diff(
            computed_dict=topology, expected_filepath=relative_path("expected_topology/ecs.json")
        )
        self.assertEqual(diff, "")

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api(None)
    def test_process_cloudformation(self):
        self.check.run()
        self.assert_executed_ok()

        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)

        stacks = list(filter(lambda x: x["type"] == "aws.cloudformation", topology[0]["components"]))
        self.assertEqual(len(stacks), 2)
        self.assertEqual(
            stacks[0]["id"],
            "arn:aws:cloudformation:eu-west-1:731070500579" +
            ":stack/stackstate-topo-publisher/71ea3f80-9919-11e9-a261-0a99a68566c4",
        )  # DIFF
        self.assertEqual(stacks[0]["data"]["StackName"], "stackstate-topo-publisher")
        self.assertTrue(stacks[0]["data"]["LastUpdatedTime"])
        self.assertEqual(stacks[0]["type"], "aws.cloudformation")  # DIFF
        self.assert_location_info(stacks[0])

        # total relations should be 14 for each stack
        relations = list(
            filter(
                lambda x: x["type"] == "has resource" and x["source_id"].startswith("arn:aws:cloudformation"),
                topology[0]["relations"],
            )
        )
        self.assertEqual(len(relations), 30)

        # assert for common sourceID and type for the relations
        self.assertEqual(relations[0]["source_id"], stacks[0]["id"])  # DIFF
        self.assertEqual(relations[0]["type"], "has resource")  # DIFF

        source_id = relations[0]["source_id"]
        # assert for lambda function relation
        self.assertEqual(self.has_relation(
            relations, source_id,
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY"
        ), True)
        # assert for kinesis stream relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1"
        ), True)
        # assert for s3 bucket relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:s3:::stackstate.com"
        ), True)
        # assert for api_stage relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:execute-api:eu-west-1:731070500579:api_1"
        ), True)
        # assert for loadbalancer relation
        self.assertEqual(self.has_relation(
            relations, source_id,
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9",
        ), True)
        # assert for target group relation
        self.assertEqual(self.has_relation(
            relations, source_id,
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/myfirsttargetgroup/28ddec997ec55d21",
        ), True)
        # assert for autoscaling group relation
        self.assertEqual(self.has_relation(
            relations, source_id,
            "awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
        ), True)
        # assert for elb classic loadbalancer  relation
        self.assertEqual(self.has_relation(
            relations, source_id, "classic_elb_classic-loadbalancer-1"
        ), True)
        # assert for rds relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase"
        ), True)
        # assert for sns topic relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:sns:eu-west-1:731070500579:my-topic-3"
        ), True)
        # assert for sqs queue relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test"
        ), True)
        # assert for dynamodb table relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:dynamodb:eu-west-1:731070500579:table/table_3"
        ), True)
        # assert for ecs cluster relation
        self.assertEqual(self.has_relation(
            relations, source_id, "arn:aws:ecs:eu-west-1:731070500579:cluster/StackState-ECS-Cluster"
        ), True)
        # assert for ec2 instance relation
        self.assertEqual(self.has_relation(
            relations, source_id, "i-0aac5bab082561475"
        ), True)

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("cloudformation")
    @patch(
        "stackstate_checks.aws_topology.aws_topology.AgentProxy.finalize_account_topology",
        dont_send_parked_relations
    )
    def test_process_cloudformation_stack_relation(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"],
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/stackstate-topo-publisher/" +
            "71ea3f80-9919-11e9-a261-0a99a68566c4",
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][0]["target_id"],
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/stackstate-topo-cwevents/" +
            "077bd960-9919-11e9-adb7-02135cc8443e",
        )  # DIFF
        self.assertEqual(topology[0]["relations"][0]["type"], "child of")  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api(None)
    def test_check(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]
        events = aggregator.events

        aws_agent_check_errors = list(filter(lambda x: x["event_type"] == "aws_agent_check_error", events))
        self.assertEqual(len(aws_agent_check_errors), 0)

        unique_types = self.unique_topology_types(topology)
        self.assertEqual(len(unique_types), 32)  # +1 for RestApi that is now emitted

    # @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    # @set_api(None)
    # def test_old_agent(self):
    #     self.check.run()
    #     self.assert_executed_ok()
    #     topology = [top.get_snapshot(self.check.check_id)]
    #     events = aggregator.events

    #     aws_agent_check_errors = list(filter(lambda x: x["event_type"] == "aws_agent_check_error", events))
    #     self.assertEqual(len(aws_agent_check_errors), 0)

    #     tosave = deepcopy(topology[0])
    #     for comp in tosave["components"]:
    #         comp["data"].pop("tags")
    #     tosave["relations"].sort(key=lambda x: x["source_id"] + "-" + x["type"] + x["target_id"])
    #     tosave["components"].sort(key=lambda x: x["type"] + "-" + x["id"])
    #     with open(relative_path('output.json'), 'wt') as f:
    #         f.write(json.dumps(tosave, sort_keys=True, default=str, indent=2))

    #     diff = compute_topologies_diff(
    #         computed_dict=topology[0], expected_filepath=relative_path("expected_topology/from_old_agent.json")
    #     )
    #     self.assertEqual(diff, "")


class TestTemplatePathedRegistry(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

    def unique_topology_types(self, topology):
        return set([c["type"] for ti in topology for c in ti["components"]])  # DIFF

    @requires_py3
    @parameterized.expand([
        ('ec2|instances vpcs security_groups', 31),
        ('ec2|instances vpn_gateways security_groups', 30),
        ('autoscaling', 31),
        ('apigateway', 27),  # all have +1 of CF link, this one has -1 because -2 stage relations + 1 api relation
        ('firehose', 31),

        ('kinesis', 31),
        ('dynamodb', 30),
        ('lambda|mappings', 30),
        ('lambda|functions', 32),  # TODO: why not same as happy flow???
        ('sqs', 31),

        ('sns', 31),
        ('redshift', 32),  # TODO: why not same as happy flow???
        ('s3', 31),
        ('rds', 30),
        ('elbv2', 29),

        ('elb', 31),
        ('ec2|vpcs vpn_gateways security_groups', 31),
        ('ecs', 29),
        ('route53domains', 31),
        ('route53', 31),
        ('cloudformation', 31),
        # ('process_cloudformation_stack_relation', 31),  # DIFF give only did relations move to cloudformation
        ('ec2|instances vpcs vpn_gateways', 31),
    ])
    @set_api(None)
    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    def test_check_error_handling(self, check_name, expected_unique_topology_types):
        try:
            with patch(
                'stackstate_checks.aws_topology.resources.ResourceRegistry.get_registry',
                wraps=get_wrapper(check_name)
            ):
                top.reset()
                aggregator.reset()
                init_config = InitConfig({
                    "aws_access_key_id": "some_key",
                    "aws_secret_access_key": "some_secret",
                    "external_id": "disable_external_id_this_is_unsafe",
                })
                instance = {
                    "role_arn": "arn:aws:iam::731070500579:role/RoleName",
                    "regions": ["global", "eu-west-1"],
                }
                self.check = AwsTopologyCheck(self.CHECK_NAME, init_config, [instance])
                self.check.run()

                topology = [top.get_snapshot(self.check.check_id)]
                events = aggregator.events

                unique_types = self.unique_topology_types(topology)
                self.assertEqual(len(unique_types), expected_unique_topology_types)
                # TODO I can't return an error when running an API partly (error handling is WIP)
                if "|" not in check_name:
                    aws_agent_check_errors = list(filter(lambda x: x['event_type'] == 'aws_agent_check_error', events))
                    self.assertEqual(len(aws_agent_check_errors), 1)
        except Exception:
            traceback.print_exc()
            raise
