import difflib
import unittest
import os
import json
from mock import patch
import dateutil.parser
import datetime
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.base import AgentCheck
from stackstate_checks.aws_topology import AwsTopologyCheck
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
    with open(relative_path(path)) as f:
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
        api, comptype = check_name.split("|", 1)
        # error class

        class error(object):
            API = "error"
            MEMORY_KEY = None

            def __init__(self, location_info, client, agent):
                pass

            def get_delete_ids(self):
                return []

            def process_all(self):
                raise Exception("Oops")

        # patch the registry
        registry[api][comptype] = error
        return registry
    return registry_wrapper


def mock_boto_calls(self, operation_name, kwarg):
    # print(operation_name)
    if operation_name == "AssumeRole":
        return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
    elif operation_name == "DescribeInstances":
        test_event = resource("json/test_describe_ec2.json")
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
        return resource("json/test_describe_security_groups.json")

    elif operation_name == "DescribeInstanceTypes":
        return resource("json/test_describe_instance_types.json")

    elif operation_name == "GetCallerIdentity":
        return resource("json/test_get_caller_identity.json")

    elif operation_name == "DescribeStacks":
        return resource("json/test_describe_cloudformation_stacks.json")

    elif operation_name == "DescribeStackResources":
        return resource("json/test_describe_cloudformation_stack_resources.json")

    elif operation_name == "ListStacks":
        return resource("json/test_cloudformation_list_stacks.json")

    elif operation_name == "DescribeInstanceHealth":
        return resource("json/test_describe_instance_health.json")

    elif operation_name == "DescribeLoadBalancers":
        if self._service_model.service_name == "elb":
            if operation_name == "DescribeLoadBalancers":
                test_event = resource("json/test_describe_load_balancers_classic.json")
                for load_balancers in test_event["LoadBalancerDescriptions"]:
                    load_balancers["CreatedTime"] = dateutil.parser.parse(load_balancers["CreatedTime"])

                return test_event

            else:
                raise ValueError("Unknown operation name", operation_name)

        else:
            test_event = resource("json/test_describe_load_balancers.json")
            for load_balancer in test_event["LoadBalancers"]:
                load_balancer["CreatedTime"] = dateutil.parser.parse(load_balancer["CreatedTime"])

            return test_event

    elif operation_name == "DescribeListeners":
        return resource("json/test_describe_listeners.json")

    elif operation_name == "DescribeTargetGroups":
        return resource("json/test_describe_target_groups.json")

    elif operation_name == "DescribeTargetHealth":
        return resource("json/test_decribe_target_health.json")

    elif operation_name == "ListBuckets":
        test_event = resource("json/test_describe_s3.json")
        for bucket in test_event["Buckets"]:
            bucket["CreationDate"] = dateutil.parser.parse(bucket["CreationDate"])
        return test_event

    elif operation_name == "DescribeDBInstances":
        test_event = resource("json/test_describe_rds_instances.json")
        for instance in test_event["DBInstances"]:
            instance["InstanceCreateTime"] = dateutil.parser.parse(instance["InstanceCreateTime"])
        return test_event

    elif operation_name == "DescribeDBClusters":
        test_event = resource("json/test_describe_rds_clusters.json")
        for cluster in test_event["DBClusters"]:
            cluster["LatestRestorableTime"] = dateutil.parser.parse(cluster["LatestRestorableTime"])
            cluster["EarliestRestorableTime"] = dateutil.parser.parse(cluster["EarliestRestorableTime"])
            cluster["ClusterCreateTime"] = dateutil.parser.parse(cluster["ClusterCreateTime"])
        return test_event

    elif operation_name == "ListFunctions":
        test_event = resource("json/test_lambda_list_functions.json")
        for fn in test_event["Functions"]:
            fn["LastModified"] = dateutil.parser.parse(fn["LastModified"])
        return test_event

    elif operation_name == "ListEventSourceMappings":
        document = resource("json/test_lambda_list_event_source_mappings.json")
        for mapping in document["EventSourceMappings"]:
            mapping["LastModified"] = datetime.datetime.fromtimestamp(mapping["LastModified"])
        return document

    elif operation_name == "ListTopics":
        return resource("json/test_sns_list_topics.json")

    elif operation_name == "ListQueues":
        return resource("json/test_sqs_list_queues.json")

    elif operation_name == "GetQueueAttributes":
        return resource("json/test_sqs_get_queue_attributes.json")

    elif operation_name == "ListQueueTags":
        return resource("json/test_sqs_list_queue_tags.json")

    elif operation_name == "GetQueueUrl":
        return resource("json/test_sqs_get_queue_url.json")

    elif operation_name == "ListMetrics":
        return resource("json/test_cw_list_metrics.json")

    elif operation_name == "ListSubscriptionsByTopic":
        return resource("json/test_sns_list_subscriptions_by_topic.json")

    elif operation_name == "GetBucketNotificationConfiguration":
        return resource("json/test_s3_get_bucket_notification_configuration.json")

    elif operation_name == "ListTables":
        return resource("json/test_dynamodb_list_tables.json")

    elif operation_name == "ListTags":
        global THROTTLING_COUNT_TAGS
        if THROTTLING_COUNT_TAGS < 50:
            THROTTLING_COUNT_TAGS += 1
            error_response = {"Error": {"Code": "RequestLimitExceeded", "Message": "Maximum sending rate exceeded"}}
            raise ClientError(error_response, operation_name)
        else:
            return resource("json/test_lambda_list_tags.json")

    elif operation_name == "ListAliases":
        return resource("json/test_lambda_list_aliases.json")

    elif operation_name == "DescribeTable":
        path_name = "json/test_dynamodb_describe_table_" + kwarg["TableName"] + ".json"
        document = resource(path_name)
        document["Table"]["CreationDateTime"] = datetime.datetime.fromtimestamp(
            document["Table"]["CreationDateTime"]
        )
        return document

    elif operation_name == "ListStreams":
        return resource("json/test_kinesis_list_streams.json")

    elif operation_name == "DescribeStreamSummary":
        path_name = "json/test_kinesis_describe_stream_summary_" + kwarg["StreamName"] + ".json"
        document = resource(path_name)
        document["StreamDescriptionSummary"]["StreamCreationTimestamp"] = datetime.datetime.fromtimestamp(
            document["StreamDescriptionSummary"]["StreamCreationTimestamp"]
        )
        return document

    elif operation_name == "ListDeliveryStreams":
        return resource("json/test_firehose_list_delivery_streams.json")

    elif operation_name == "DescribeDeliveryStream":
        path_name = "json/test_firehose_describe_delivery_stream_" + kwarg["DeliveryStreamName"] + ".json"
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
        return resource("json/test_apigateway_get_rest_apis.json")

    elif operation_name == "GetStages":
        return resource("json/test_apigateway_get_stages.json")

    elif operation_name == "GetResources":
        path_name = "json/test_apigateway_get_resources_" + kwarg["restApiId"] + ".json"
        return resource(path_name)

    elif operation_name == "GetMethod":
        path_name = "json/test_apigateway_get_method_" + kwarg["httpMethod"].lower() + ".json"
        return resource(path_name)

    elif operation_name == "ListDomains":
        document = resource("json/test_route53domains_list_domains.json")
        for domain in document["Domains"]:
            domain["Expiry"] = datetime.datetime.fromtimestamp(domain["Expiry"])
        return document

    elif operation_name == "ListHostedZones":
        return resource("json/test_route53_list_hosted_zones.json")

    elif operation_name == "GetHostedZone":
        return resource("json/test_route53_get_hosted_zone.json")

    elif operation_name == "ListResourceRecordSets":
        return resource("json/test_route53_list_resource_record_sets.json")

    elif operation_name == "DescribeAutoScalingGroups":
        document = resource("json/test_autoscaling_describe_auto_scaling_groups.json")
        for auto_scaling_group in document["AutoScalingGroups"]:
            auto_scaling_group["CreatedTime"] = dateutil.parser.parse(auto_scaling_group["CreatedTime"])
        return document

    elif operation_name == "DescribeVpcs":
        return resource("json/test_ec2_describe_vpcs.json")

    elif operation_name == "DescribeSubnets":
        return resource("json/test_ec2_describe_subnets.json")

    elif operation_name == "DescribeVpnGateways":
        return resource("json/test_ec2_describe_vpn_gateways.json")

    elif operation_name == "GetBucketLocation":
        return resource("json/test_s3_get_bucket_location.json")

    elif operation_name == "ListTagsForStream":
        return resource("json/test_kinesis_list_tags_for_stream.json")

    elif operation_name == "ListClusters":
        return resource("json/test_ecs_list_clusters.json")

    elif operation_name == "DescribeClusters":
        # Unfortunately boto3 uses the same operation name for both ECS cluster and Redshift Cluster
        if self._service_model.service_name == "ecs":
            return resource("json/test_ecs_describe_clusters.json")
        else:
            return resource("json/test_redshift_describe_clusters.json")

    elif operation_name == "ListServices":
        return resource("json/test_ecs_list_services.json")

    elif operation_name == "DescribeServices":
        document = resource("json/test_ecs_describe_services.json")
        for service in document["services"]:
            service["createdAt"] = dateutil.parser.parse(service["createdAt"])

            for deployment in service["deployments"]:
                deployment["createdAt"] = dateutil.parser.parse(deployment["createdAt"])
                deployment["updatedAt"] = dateutil.parser.parse(deployment["updatedAt"])

            for event in service["events"]:
                event["createdAt"] = dateutil.parser.parse(event["createdAt"])
        return document

    elif operation_name == "ListTagsOfResource":
        return resource("json/test_dynamodb_list_tags_of_resource.json")

    elif operation_name == "ListTasks":
        return resource("json/test_ecs_list_tasks.json")

    elif operation_name == "DescribeTasks":
        document = resource("json/test_ecs_describe_tasks.json")

        for task in document["tasks"]:
            task["createdAt"] = dateutil.parser.parse(task["createdAt"])
            task["startedAt"] = dateutil.parser.parse(task["startedAt"])
            task["connectivityAt"] = dateutil.parser.parse(task["connectivityAt"])
            task["pullStartedAt"] = dateutil.parser.parse(task["pullStartedAt"])
            task["pullStoppedAt"] = dateutil.parser.parse(task["pullStoppedAt"])

        return document

    elif operation_name == "ListContainerInstances":
        return resource("json/test_ecs_list_container_instances.json")

    elif operation_name == "DescribeContainerInstances":
        return resource("json/test_ecs_describe_container_instances.json")

    elif operation_name == "ListTagsForResource":
        if self._service_model.service_name == "rds":
            return resource("json/test_rds_list_tags_for_resource.json")
        elif self._service_model.service_name == "route53":
            return resource("json/test_route53_list_tags_for_resource.json")
        else:
            return resource("json/test_sns_list_tags_for_resource.json")
    elif operation_name == "DescribeTags":
        return resource("json/test_elbv2_describe_tags.json")

    elif operation_name == "GetServiceGraph":
        return resource("json/test_xray_get_service_graph.json")

    elif operation_name == "GetTraceSummaries":
        return resource("json/test_xray_get_trace_summaries.json")

    elif operation_name == "ListTagsForDomain":
        return resource("json/test_route53_domain_tags.json")

    elif operation_name == "ListTagsForDeliveryStream":
        return resource("json/test_firehose_deliverystream_tags.json")
    else:
        raise ValueError("Unknown operation name", operation_name)


def compute_topologies_diff(computed_dict, expected_filepath):
    # print(topology)
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
        #     f.write(json.dumps(top, sort_keys=True, default=str, indent=2))
        topology = json.dumps(computed_dict, default=str, indent=2, sort_keys=True)
        expected_topology = json.dumps(top, default=str, indent=2, sort_keys=True)
        delta = difflib.unified_diff(a=expected_topology.strip().splitlines(), b=topology.strip().splitlines())
        # for line in delta:
        #     print(line)
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
        cfg = {
            "aws_access_key_id": "some_key",
            "aws_secret_access_key": "some_secret",
            "role_arn": "some_role",
            "account_id": "731070500579",
            "region": "eu-west-1",
        }
        if method.api:
            cfg.update({"apis_to_run": [method.api]})
        self.check = AwsTopologyCheck(self.CHECK_NAME, cfg, instances=[cfg])
        self.mock_object.side_effect = mock_boto_calls

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("ec2|aws.ec2")
    def test_process_ec2(self):
        test_instance_id = "i-0aac5bab082561475"
        test_instance_type = "m4.xlarge"
        test_public_ip = "172.30.0.96"
        test_public_dns = "ec2-172-30-0-96.eu-west-1.compute.amazonaws.com"
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        events = aggregator.events

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 2)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(topology[0]["components"][0]["id"], test_instance_id)  # DIFF was externalId
        self.assertEqual(topology[0]["components"][0]["data"]["InstanceId"], test_instance_id)
        self.assertEqual(topology[0]["components"][0]["data"]["InstanceType"], test_instance_type)
        self.assertIsNotNone(topology[0]['components'][0]['data']['Tags'])
        self.assertEqual(topology[0]['components'][0]['data']['Tags']['host'], test_instance_id)
        self.assertEqual(topology[0]['components'][0]['data']['Tags']['instance-id'], test_instance_id)
        self.assertEqual(topology[0]['components'][0]['data']['Tags']['private-ip'], test_public_ip)
        self.assertEqual(topology[0]['components'][0]['data']['Tags']['fqdn'], test_public_dns)
        self.assertEqual(topology[0]['components'][0]['data']['Tags']['public-ip'], test_public_ip)
        self.assertEqual(topology[0]["components"][0]["type"], "aws.ec2")  # DIFF was ['type']['name']
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            [
                "urn:host:/{}".format(test_instance_id),
                "arn:aws:ec2:{}:731070500579:instance/{}".format(TEST_REGION, test_instance_id),
                "urn:host:/{}".format(test_public_dns),
                "urn:host:/{}".format(test_public_ip),
            ],
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["host"], test_instance_id)
        self.assertEqual(events[0]["tags"], ["state:stopped"])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("elbv2|aws.elb_v2")
    def test_process_elb_v2_target_group_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        instance_a = "i-0a7182087df63a90b"
        instance_b = "i-0d857740370079c95"

        # ELB Target Group Instance A
        self.assertEqual(
            topology[0]["components"][2]["id"], "urn:aws/target-group-instance/" + instance_a
        )  # DIFF was externalId
        self.assertEqual(topology[0]["components"][2]["data"]["URN"][0], instance_a)
        self.assertEqual(
            topology[0]["components"][2]["type"], "aws.elb_v2_target_group_instance"
        )  # DIFF was ['type']['name']

        # ELB Target Group Instance B
        self.assertEqual(
            topology[0]["components"][3]["id"], "urn:aws/target-group-instance/" + instance_b
        )  # DIFF was externalId
        self.assertEqual(topology[0]["components"][3]["data"]["URN"][0], instance_b)
        self.assertEqual(
            topology[0]["components"][3]["type"], "aws.elb_v2_target_group_instance"
        )  # DIFF was externalId

        # Load Balancer A and Target Group A relationship test
        self.assertEqual(
            topology[0]["relations"][4]["target_id"], "urn:aws/target-group-instance/" + instance_a
        )  # DIFF was targetId
        self.assertEqual(
            topology[0]["relations"][4]["source_id"],
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/myfirsttargetgroup/28ddec997ec55d21",
        )  # DIFF was sourceId

        # Load Balancer B and Target Group B relationship test
        self.assertEqual(
            topology[0]["relations"][5]["target_id"], "urn:aws/target-group-instance/" + instance_b
        )  # DIFF was targetId
        self.assertEqual(
            topology[0]["relations"][5]["source_id"],
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/myfirsttargetgroup/28ddec997ec55d21",
        )  # DIFF was sourceId

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("elb|aws.elb_classic")
    def test_process_elb_classic(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]

        events = aggregator.events

        # todo: add test which asserts that the relation corresponds with the component info.

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(events), 2)
        self.assertEqual(len(topology[0]["relations"]), 4)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(topology[0]["components"][0]["data"]["LoadBalancerName"], "classic-loadbalancer-1")
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"]["stackstate-environment"], "Production")
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            [
                "arn:aws:elasticloadbalancing:{}:731070500579:loadbalancer/{}".format(
                    TEST_REGION, "classic-loadbalancer-1"
                )
            ],
        )

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("s3|aws.s3_bucket")
    def test_process_s3(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        target_id = (
            "arn:aws:lambda:eu-west-1:731070500579:"
            + "function:com-stackstate-prod-s-NotifyBucketEventsHandle-1W0B5NSZYJ3G1"
        )

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 4)
        self.assertEqual(topology[0]["relations"][0]["source_id"], "arn:aws:s3:::stackstate.com")  # DIFF was sourceId
        self.assertEqual(topology[0]["relations"][0]["target_id"], target_id)  # DIFF was targetId
        self.assertEqual(topology[0]["relations"][0]["type"], "uses service")  # DIFF was ['type']['name']
        self.assertEqual(topology[0]["relations"][1]["source_id"], "arn:aws:s3:::stackstate.com")  # DIFF was sourceId
        self.assertEqual(topology[0]["relations"][1]["target_id"], target_id)  # DIFF was targetId
        self.assertEqual(topology[0]["relations"][1]["type"], "uses service")  # DIFF was ['type']['name']
        self.assertEqual(topology[0]["relations"][2]["source_id"], "arn:aws:s3:::binx.io")  # DIFF was sourceId
        self.assertEqual(topology[0]["relations"][2]["target_id"], target_id)  # DIFF was targetId
        self.assertEqual(topology[0]["relations"][2]["type"], "uses service")  # DIFF was ['type']['name']
        self.assertEqual(topology[0]["relations"][3]["source_id"], "arn:aws:s3:::binx.io")  # DIFF was sourceId
        self.assertEqual(topology[0]["relations"][3]["target_id"], target_id)  # DIFF was targetId
        self.assertEqual(topology[0]["relations"][3]["type"], "uses service")  # DIFF was ['type']['name']
        self.assertEqual(len(topology[0]["components"]), 2)
        self.assertEqual(topology[0]["components"][0]["id"], "arn:aws:s3:::stackstate.com")  # DIFF was externalId
        self.assertEqual(topology[0]["components"][0]["type"], "aws.s3_bucket")  # DIFF was ['type']['name']
        self.assertEqual(topology[0]["components"][0]["data"]["Name"], "stackstate.com")
        self.assert_location_info(topology[0]["components"][0])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("rds|aws.rds_cluster")
    def test_process_rds(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()
        events = aggregator.events

        self.assertEqual(len(events), 0)
        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 6)
        self.assertEqual(len(topology[0]["components"]), 3)
        self.assertEqual(
            topology[0]["components"][1]["id"], "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase-eu-west-1c"
        )  # DIFF was exteralId
        self.assertEqual(topology[0]["components"][1]["data"]["DBInstanceIdentifier"], "productiondatabase-eu-west-1c")
        self.assertEqual(topology[0]["components"][1]["data"]["Name"], "productiondatabase-eu-west-1c")
        self.assert_stream_dimensions(
            topology[0]["components"][1], [{"Key": "DBInstanceIdentifier", "Value": "productiondatabase-eu-west-1c"}]
        )

        self.assertEqual(
            topology[0]["components"][2]["data"]["DBClusterArn"],
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
        )
        self.assertEqual(
            topology[0]["components"][2]["data"]["Name"],
            "arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster",
        )
        self.assert_stream_dimensions(
            topology[0]["components"][2], [{"Key": "DBClusterIdentifier", "Value": "productiondatabasecluster"}]
        )

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("lambda|aws.lambda")
    def test_process_lambda(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(topology[0]["relations"], [])
        self.assertEqual(len(topology[0]["components"]), 6)
        self.assertEqual(
            topology[0]["components"][0]["id"],
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
        )  # DIFF was externalId
        self.assertEqual(topology[0]["components"][0]["type"], "aws.lambda")  # DIFF was ['type']['name']
        self.assertEqual(
            topology[0]["components"][0]["data"]["FunctionName"], "com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY"
        )
        self.assertEqual(
            topology[0]["components"][1]["id"],
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY:old",
        )  # DIFF was externalId
        self.assertEqual(topology[0]["components"][1]["type"], "aws.lambda.alias")  # DIFF was ['type']['name']
        self.assertEqual(
            topology[0]["components"][1]["data"]["Function"]["FunctionName"],
            "com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
        )
        self.assertEqual(topology[0]["components"][1]["data"]["Name"], "old")
        self.assert_location_info(topology[0]["components"][0])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("sns|aws.sns")
    def test_process_sns(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        base_target_id = "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-"

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 5)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-1"
        )  # DIFF was targetId sourceId (also below)
        self.assertEqual(topology[0]["relations"][0]["target_id"], base_target_id + "TopicHandler-11EWA2GN9YNLL")
        self.assertEqual(topology[0]["relations"][1]["source_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-2")
        self.assertEqual(topology[0]["relations"][1]["target_id"], base_target_id + "TopicHandler-21EWA2GN9YNLL")
        self.assertEqual(topology[0]["relations"][2]["source_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-3")
        self.assertEqual(topology[0]["relations"][2]["target_id"], base_target_id + "TopicHandler-31EWA2GN9YNLL")
        self.assertEqual(topology[0]["relations"][3]["source_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-3")
        self.assertEqual(topology[0]["relations"][3]["target_id"], base_target_id + "TopicHandler-41EWA2GN9YNLL")
        self.assertEqual(topology[0]["relations"][4]["source_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-3")
        self.assertEqual(
            topology[0]["relations"][4]["target_id"], "arn:aws:sqs:eu-west-1:508573134510:STS_stackpack_test"
        )
        self.assertEqual(len(topology[0]["components"]), 4)
        self.assertEqual(
            topology[0]["components"][0]["id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-1"
        )  # DIFF externalId
        self.assertEqual(topology[0]["components"][0]["type"], "aws.sns")  # DIFF was ['type']['name']
        self.assertEqual(
            topology[0]["components"][0]["data"]["TopicArn"], "arn:aws:sns:eu-west-1:731070500579:my-topic-1"
        )
        self.assertEqual(topology[0]["components"][0]["data"]["Name"], "arn:aws:sns:eu-west-1:731070500579:my-topic-1")
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"]["SnsTagKey"], "SnsTagValue")
        self.assert_stream_dimensions(topology[0]["components"][0], [{"Key": "TopicName", "Value": "my-topic-1"}])

        self.assert_location_info(topology[0]["components"][0])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("sqs|aws.sqs")
    def test_process_sqs(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            topology[0]["components"][0]["id"], "arn:aws:sqs:eu-west-1:508573134510:STS_stackpack_test"
        )  # DIFF externalId
        self.assertEqual(topology[0]["components"][0]["type"], "aws.sqs")  # DIFF was ['type']['name']
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"], {"a": "b"})
        self.assertEqual(
            topology[0]["components"][0]["data"]["Name"],
            "https://eu-west-1.queue.amazonaws.com/508573134510/STS_stackpack_test",
        )
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            ["https://eu-west-1.queue.amazonaws.com/508573134510/STS_stackpack_test"],
        )

        self.assert_stream_dimensions(
            topology[0]["components"][0], [{"Key": "QueueName", "Value": "STS_stackpack_test"}]
        )

        self.assert_location_info(topology[0]["components"][0])

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
    @set_api("lambda|aws.lambda.event_source_mapping")
    def test_process_lambda_event_source_mappings(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertEqual(len(topology[0]["relations"]), 2)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"],
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-PersonIdDynamoDBHandler-6KMIBXKKKCEZ",
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][0]["target_id"],
            "arn:aws:dynamodb:eu-west-1:731070500579:table/table_1/stream/2018-05-17T08:09:27.110",
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][1]["source_id"],
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-PersonCreatedKinesisHand-19T8EJADX2DE",
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][1]["target_id"], "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1"
        )  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("kinesis|aws.kinesis")
    def test_process_kinesis_streams(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        base_stream_arn = "arn:aws:kinesis:eu-west-1:731070500579:stream/"

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 0)
        self.assertEqual(len(topology[0]["components"]), 4)
        self.assertEqual(topology[0]["components"][0]["id"], base_stream_arn + "stream_1")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.kinesis")  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamARN"],
            "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1",
        )
        self.assertEqual(topology[0]["components"][1]["id"], base_stream_arn + "stream_2")  # DIFF
        self.assertEqual(topology[0]["components"][1]["type"], "aws.kinesis")  # DIFF
        self.assertEqual(topology[0]["components"][2]["id"], base_stream_arn + "stream_3")  # DIFF
        self.assertEqual(topology[0]["components"][2]["type"], "aws.kinesis")  # DIFF
        self.assertEqual(topology[0]["components"][3]["id"], base_stream_arn + "stream_4")  # DIFF
        self.assertEqual(topology[0]["components"][3]["type"], "aws.kinesis")  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("firehose|aws.firehose")
    def test_process_firehose(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        firehose_arn_prefix = "arn:aws:firehose:eu-west-1:731070500579:deliverystream/"
        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 2)
        self.assertEqual(topology[0]["components"][0]["id"], firehose_arn_prefix + "firehose_1")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.firehose")  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["DeliveryStreamDescription"]["DeliveryStreamARN"],
            "arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1",
        )
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"]["SomeKey"], "SomeValue")
        self.assert_stream_dimensions(
            topology[0]["components"][0],
            [{"Key": "DeliveryStreamName", "Value": "dnv-sam-seed-button-clicked-firehose"}],
        )
        self.assertEqual(topology[0]["components"][1]["id"], firehose_arn_prefix + "firehose_2")  # DIFF
        self.assertEqual(topology[0]["components"][1]["type"], "aws.firehose")  # DIFF
        self.assertEqual(len(topology[0]["relations"]), 3)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"], "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1"
        )  # DIFF
        self.assertEqual(topology[0]["relations"][0]["target_id"], firehose_arn_prefix + "firehose_1")  # DIFF
        self.assertEqual(topology[0]["relations"][1]["source_id"], firehose_arn_prefix + "firehose_1")  # DIFF
        self.assertEqual(topology[0]["relations"][1]["target_id"], "arn:aws:s3:::firehose-bucket_1")  # DIFF
        self.assertEqual(topology[0]["relations"][2]["source_id"], firehose_arn_prefix + "firehose_2")  # DIFF
        self.assertEqual(topology[0]["relations"][2]["target_id"], "arn:aws:s3:::firehose-bucket_2")  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("apigateway|aws.apigateway.stage")
    def test_process_api_gateway(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        stage_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}"
        resource_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/*/hello"
        method_arn_prefix = "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage{}/{}/hello"
        lambda_arn_prefix = "arn:aws:lambda:eu-west-1:731070500579:function:{}"
        sqs_arn = "arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test"

        self.assertEqual(len(topology), 1)
        # we have 2 stages
        for n in range(0, 2):
            self.assertEqual(topology[0]["components"][0 + (n * 15)]["id"], stage_arn_prefix.format(n + 1))  # DIFF
            self.assertEqual(topology[0]["components"][0 + (n * 15)]["type"], "aws.apigateway.stage")  # DIFF
            self.assertEqual(topology[0]["components"][0 + (n * 15)]["data"]["RestApiName"], "api_1")
            self.assertEqual(
                topology[0]["components"][0 + (n * 15)]["data"]["Tags"]["StageTagKey" + str(n + 1)],
                "StageTagValue" + str(n + 1),
            )
            self.assert_stream_dimensions(
                topology[0]["components"][0 + (n * 15)],
                [
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][0 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(topology[0]["components"][1 + (n * 15)]["id"], resource_arn_prefix.format(n + 1))  # DIFF
            self.assertEqual(topology[0]["components"][1 + (n * 15)]["type"], "aws.apigateway.resource")  # DIFF
            self.assertEqual(topology[0]["components"][1 + (n * 15)]["data"]["Path"], "/hello")
            self.assert_stream_dimensions(
                topology[0]["components"][1 + (n * 15)],
                [
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][1 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(
                topology[0]["components"][2 + (n * 15)]["id"], method_arn_prefix.format(n + 1, "DELETE")
            )  # DIFF
            self.assertEqual(topology[0]["components"][2 + (n * 15)]["type"], "aws.apigateway.method")  # DIFF
            self.assertEqual(topology[0]["components"][2 + (n * 15)]["data"]["HttpMethod"], "DELETE")
            self.assert_stream_dimensions(
                topology[0]["components"][2 + (n * 15)],
                [
                    {"Key": "Method", "Value": topology[0]["components"][2 + (n * 15)]["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": topology[0]["components"][2 + (n * 15)]["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][2 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(
                topology[0]["components"][3 + (n * 15)]["id"], method_arn_prefix.format(n + 1, "GET")
            )  # DIFF
            self.assertEqual(topology[0]["components"][3 + (n * 15)]["type"], "aws.apigateway.method")  # DIFF
            self.assertEqual(topology[0]["components"][3 + (n * 15)]["data"]["HttpMethod"], "GET")
            self.assert_stream_dimensions(
                topology[0]["components"][3 + (n * 15)],
                [
                    {"Key": "Method", "Value": topology[0]["components"][3 + (n * 15)]["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": topology[0]["components"][3 + (n * 15)]["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][3 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(
                topology[0]["components"][4 + (n * 15)]["id"], method_arn_prefix.format(n + 1, "PATCH")
            )  # DIFF
            self.assertEqual(topology[0]["components"][4 + (n * 15)]["type"], "aws.apigateway.method")  # DIFF
            self.assertEqual(topology[0]["components"][4 + (n * 15)]["data"]["HttpMethod"], "PATCH")
            self.assert_stream_dimensions(
                topology[0]["components"][4 + (n * 15)],
                [
                    {"Key": "Method", "Value": topology[0]["components"][4 + (n * 15)]["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": topology[0]["components"][4 + (n * 15)]["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][4 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(
                topology[0]["components"][5 + (n * 15)]["id"], method_arn_prefix.format(n + 1, "POST")
            )  # DIFF
            self.assertEqual(topology[0]["components"][5 + (n * 15)]["type"], "aws.apigateway.method")  # DIFF
            self.assertEqual(topology[0]["components"][5 + (n * 15)]["data"]["HttpMethod"], "POST")
            self.assert_stream_dimensions(
                topology[0]["components"][5 + (n * 15)],
                [
                    {"Key": "Method", "Value": topology[0]["components"][5 + (n * 15)]["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": topology[0]["components"][5 + (n * 15)]["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][5 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

            self.assertEqual(topology[0]["components"][6 + (n * 15)]["id"], "urn:service:/84.35.236.89")  # DIFF
            self.assertEqual(
                topology[0]["components"][6 + (n * 15)]["type"], "aws.apigateway.method.http.integration"
            )  # DIFF

            self.assertEqual(
                topology[0]["components"][7 + (n * 15)]["id"], method_arn_prefix.format(n + 1, "PUT")
            )  # DIFF
            self.assertEqual(topology[0]["components"][7 + (n * 15)]["type"], "aws.apigateway.method")  # DIFF
            self.assertEqual(topology[0]["components"][7 + (n * 15)]["data"]["HttpMethod"], "PUT")
            self.assert_stream_dimensions(
                topology[0]["components"][7 + (n * 15)],
                [
                    {"Key": "Method", "Value": topology[0]["components"][7 + (n * 15)]["data"]["HttpMethod"]},
                    {"Key": "Resource", "Value": topology[0]["components"][7 + (n * 15)]["data"]["Path"]},
                    {"Key": "Stage", "Value": "stage{}".format(n + 1)},
                    {"Key": "ApiName", "Value": topology[0]["components"][7 + (n * 15)]["data"]["RestApiName"]},
                ],
            )

        self.assertEqual(len(topology[0]["components"]), 30)

        # we have 2 stages
        for n in range(0, 2):
            self.assertEqual(
                topology[0]["relations"][0 + (n * 22)]["source_id"], stage_arn_prefix.format(n + 1)
            )  # DIFF
            self.assertEqual(
                topology[0]["relations"][0 + (n * 22)]["target_id"], resource_arn_prefix.format(n + 1)
            )  # DIFF
            self.assert_method_relations(
                topology,
                method_arn_prefix.format(n + 1, "PATCH"),
                resource_arn_prefix.format(n + 1),
                sqs_arn,
                5 + (n * 22),
            )
            self.assert_method_relations(
                topology,
                method_arn_prefix.format(n + 1, "PUT"),
                resource_arn_prefix.format(n + 1),
                lambda_arn_prefix.format("PutHello-1LUD3ESBOR6EY"),
                9 + (n * 22),
            )
            self.assert_method_relations(
                topology,
                method_arn_prefix.format(n + 1, "POST"),
                resource_arn_prefix.format(n + 1),
                "urn:service:/84.35.236.89",
                7 + (n * 22),
            )
            self.assert_method_relations(
                topology,
                method_arn_prefix.format(n + 1, "GET"),
                resource_arn_prefix.format(n + 1),
                lambda_arn_prefix.format("GetHello-1CZ5O92284Z69"),
                3 + (n * 22),
            )
            self.assert_method_relations(
                topology,
                method_arn_prefix.format(n + 1, "DELETE"),
                resource_arn_prefix.format(n + 1),
                lambda_arn_prefix.format("DeleteHello-1LDFJCU54ZL5"),
                1 + (n * 22),
            )

        self.assertEqual(len(topology[0]["relations"]), 44)

    def assert_method_relations(self, topology, method_arn, resource_arn, lambda_arn, index):
        self.assertEqual(topology[0]["relations"][index]["source_id"], resource_arn)  # DIFF
        self.assertEqual(topology[0]["relations"][index]["target_id"], method_arn)  # DIFF
        self.assertEqual(topology[0]["relations"][index + 1]["source_id"], method_arn)  # DIFF
        self.assertEqual(topology[0]["relations"][index + 1]["target_id"], lambda_arn)  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("route53domains|aws.route53.domain")
    def test_process_route53_domains(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(topology[0]["components"][0]["id"], "stackstate.com")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.route53.domain")  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"], ["arn:aws:route53::731070500579:domain/stackstate.com"]
        )
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"]["Route53DomainTagKey"], "Route53DomainTagValue")
        self.assertEqual(topology[0]["components"][0]["data"]["DomainName"], "stackstate.com")
        self.assert_location_info(topology[0]["components"][0])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("route53|aws.route53.hostedzone")
    def test_process_route_53_hosted_zones(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(topology[0]["components"][0]["id"], "/hostedzone/Z4OKCQBA0VS63")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.route53.hostedzone")  # DIFF
        self.assertEqual(topology[0]["components"][0]["data"]["URN"], ["arn:aws:route53:::hostedzone/Z4OKCQBA0VS63"])
        self.assertEqual(topology[0]["components"][0]["data"]["Tags"]["ResourceTagKey"], "ResourceTagValue")
        self.assertEqual(topology[0]["components"][0]["data"]["HostedZone"]["Name"], "serverless.nl.")
        self.assert_location_info(topology[0]["components"][0])

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("autoscaling|aws.autoscaling")
    def test_process_auto_scaling(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        # TODO this needs to be fixed in go, delete_ids need to be passed
        topology[0]["delete_ids"] = self.check.delete_ids
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            topology[0]["components"][0]["data"]["AutoScalingGroupARN"],
            "arn:aws:autoscaling:eu-west-1:731070500579:autoScalingGroup:e1155c2b-016a-40ad-8cba-2423c349574b:"
            + "autoScalingGroupName/awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
        )
        self.assertEqual(
            topology[0]["components"][0]["id"],
            "arn:aws:autoscaling:eu-west-1:731070500579:autoScalingGroup:e1155c2b-016a-40ad-8cba-2423c349574b:"
            + "autoScalingGroupName/awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
        )  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.autoscaling")  # DIFF
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(len(topology[0]["delete_ids"]), 3)
        self.assertEqual(len(topology[0]["relations"]), 4)

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("ec2|aws.security-group")
    def test_process_security_group(self):
        first_sg_group_id = "sg-002abe0b505ad7002"
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 49)
        self.assertEqual(len(topology[0]["relations"]), 49)
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:security-group/{}".format(TEST_REGION, first_sg_group_id)],
        )
        self.assertEqual(topology[0]["components"][0]["id"], first_sg_group_id)  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["Version"],
            "98607ca852bd0bd895f1a5301130904d2f64bb53b9698976b2793b009614b7b1",
        )  # DIFF was "cb3857fbd9fc6d5c0509f218d8f7abe0ea3a00499cda699b6cc4010be4d16780"
        # was caused by type.name, externalId and tag integration
        self.assertEqual(topology[0]["components"][0]["data"]["Name"], "network-ALBSecurityGroupPublic-1DNVWX102724V")

    def mock_security_group_2_boto_calls(self, operation_name, kwarg):
        # print(operation_name)
        if operation_name == "AssumeRole":
            return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
        elif operation_name == "DescribeSecurityGroups":
            return resource("json/test_describe_security_groups_2.json")
        elif operation_name == "DescribeInstanceTypes":
            return resource("json/test_describe_instance_types.json")
        elif operation_name == "GetCallerIdentity":
            return resource("json/test_get_caller_identity.json")

    @patch("botocore.client.BaseClient._make_api_call", mock_security_group_2_boto_calls)
    @set_api("ec2|aws.security-group")
    def test_process_security_group_version_hash_is_not_affected_by_order(self):
        first_sg_group_id = "sg-002abe0b505ad7002"
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 49)
        self.assertEqual(len(topology[0]["relations"]), 49)
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:security-group/{}".format(TEST_REGION, first_sg_group_id)],
        )
        self.assertEqual(topology[0]["components"][0]["id"], first_sg_group_id)  # DIFF
        self.assertEqual(
            topology[0]["components"][0]["data"]["Version"],
            "c4867128bc023a41cb70b1a5b40f6b28c4f9554a2828cfd3fe920fbc27b9b4c0",
        )  # DIFF was "cb3857fbd9fc6d5c0509f218d8f7abe0ea3a00499cda699b6cc4010be4d16780"
        # was caused by type.name, externalId and tag integration
        self.assertEqual(topology[0]["components"][0]["data"]["Name"], "network-ALBSecurityGroupPublic-1DNVWX102724V")

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("ec2|aws.vpc")
    def test_process_vpcs(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assert_executed_ok()

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 2)
        self.assertEqual(topology[0]["components"][0]["id"], "vpc-6b25d10e")  # DIFF
        self.assertEqual(topology[0]["components"][0]["type"], "aws.vpc")  # DIFF
        self.assertEqual(topology[0]["components"][0]["data"]["VpcId"], "vpc-6b25d10e")
        self.assertEqual(
            topology[0]["components"][0]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:vpc/{}".format(TEST_REGION, "vpc-6b25d10e")],
        )
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(topology[0]["components"][1]["id"], "subnet-9e4be5f9")  # DIFF
        self.assertEqual(topology[0]["components"][1]["type"], "aws.subnet")  # DIFF
        self.assertEqual(topology[0]["components"][1]["data"]["SubnetId"], "subnet-9e4be5f9")
        self.assertEqual(topology[0]["components"][1]["data"]["Tags"], {"Name": "demo-deployments"})
        self.assertEqual(
            topology[0]["components"][1]["data"]["URN"],
            ["arn:aws:ec2:{}:731070500579:subnet/{}".format(TEST_REGION, "subnet-9e4be5f9")],
        )
        self.assert_location_info(topology[0]["components"][1])
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(topology[0]["relations"][0]["source_id"], "subnet-9e4be5f9")  # DIFF
        self.assertEqual(topology[0]["relations"][0]["target_id"], "vpc-6b25d10e")  # DIFF

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("ec2|aws.vpngateway")
    def test_process_vpn_gateways(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(topology[0]["components"][0]["id"], "vgw-b8c2fccc")  # DIFF
        self.assertEqual(topology[0]["components"][0]["data"]["VpnGatewayId"], "vgw-b8c2fccc")
        self.assertEqual(topology[0]["components"][0]["type"], "aws.vpngateway")  # DIFF
        self.assert_location_info(topology[0]["components"][0])
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(topology[0]["relations"][0]["source_id"], "vgw-b8c2fccc")  # DIFF
        self.assertEqual(topology[0]["relations"][0]["target_id"], "vpc-6b25d10e")  # DIFF

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

        # assert for lambda function relation
        self.assertEqual(
            relations[0]["target_id"],
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
        )
        # assert for kinesis stream relation
        self.assertEqual(relations[1]["target_id"], "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1")
        # assert for s3 bucket relation
        self.assertEqual(relations[2]["target_id"], "arn:aws:s3:::stackstate.com")
        # assert for api_stage stage1 relation
        self.assertEqual(relations[3]["target_id"], "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage1")
        # assert for api_stage stage2 relation
        self.assertEqual(relations[4]["target_id"], "arn:aws:execute-api:eu-west-1:731070500579:api_1/stage2")
        # assert for target group relation
        self.assertEqual(
            relations[5]["target_id"],
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/myfirsttargetgroup/28ddec997ec55d21",
        )
        # assert for loadbalancer relation
        self.assertEqual(
            relations[6]["target_id"],
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9",
        )
        # assert for autoscaling group relation
        self.assertEqual(
            relations[7]["target_id"],
            "arn:aws:autoscaling:eu-west-1:731070500579:autoScalingGroup:e1155c2b-016a-40ad-8cba-2423c349574b:" +
            "autoScalingGroupName/awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
        )
        # assert for elb classic loadbalancer  relation
        self.assertEqual(relations[8]["target_id"], "classic_elb_classic-loadbalancer-1")
        # assert for rds relation
        self.assertEqual(relations[9]["target_id"], "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase")
        # assert for sns topic relation
        self.assertEqual(relations[10]["target_id"], "arn:aws:sns:eu-west-1:731070500579:my-topic-3")
        # assert for sqs queue relation
        self.assertEqual(relations[11]["target_id"], "arn:aws:sqs:eu-west-1:508573134510:STS_stackpack_test")
        # assert for dynamodb table relation
        self.assertEqual(relations[12]["target_id"], "arn:aws:dynamodb:eu-west-1:731070500579:table/table_3")
        # assert for ecs cluster relation
        self.assertEqual(
            relations[13]["target_id"], "arn:aws:ecs:eu-west-1:850318095909:cluster/StackState-ECS-Cluster"
        )
        # assert for ec2 instance relation
        self.assertEqual(relations[14]["target_id"], "i-0aac5bab082561475")

    @patch("botocore.client.BaseClient._make_api_call", mock_boto_calls)
    @set_api("cloudformation|aws.cloudformation")
    def test_process_cloudformation_stack_relation(self):
        self.check.run()
        self.assert_executed_ok()
        topology = [top.get_snapshot(self.check.check_id)]

        self.assertEqual(len(topology), 1)
        self.assertEqual(len(topology[0]["relations"]), 1)
        self.assertEqual(
            topology[0]["relations"][0]["source_id"],
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/stackstate-topo-publisher/71ea3f80-9919",
        )  # DIFF
        self.assertEqual(
            topology[0]["relations"][0]["target_id"],
            "arn:aws:cloudformation:eu-west-1:731070500579:stack/some-parent-stack-id/71ea3a23-9919-54ad",
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
        self.assertEqual(len(unique_types), 31)

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
        ('ec2|aws.vpngateway', 30),
        ('ec2|aws.vpc', 29),
        ('autoscaling|aws.autoscaling', 30),
        ('apigateway|aws.apigateway.stage', 27),
        ('firehose|aws.firehose', 30),

        ('kinesis|aws.kinesis', 30),
        ('dynamodb|aws.dynamodb', 29),
        ('lambda|aws.lambda', 29),
        ('lambda|aws.lambda.event_source_mapping', 31),  # TODO: why not same as happy flow???
        ('sqs|aws.sqs', 30),

        ('sns|aws.sns', 30),
        ('redshift|aws.redshift', 31),  # TODO: why not same as happy flow???
        ('s3|aws.s3_bucket', 30),
        ('rds|aws.rds_cluster', 29),
        ('elbv2|aws.elb_v2', 28),

        ('elb|aws.elb_classic', 30),
        ('ec2|aws.ec2', 30),
        ('ecs|aws.ecs.cluster', 28),
        ('route53domains|aws.route53.domain', 30),
        ('route53|aws.route53.hostedzone', 30),
        ('cloudformation|aws.cloudformation', 30),
        # ('process_cloudformation_stack_relation', 31),  # DIFF give only did relations move to cloudformation
        ('ec2|aws.security-group', 30),
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
                cfg = {
                    "aws_access_key_id": "some_key",
                    "aws_secret_access_key": "some_secret",
                    "role_arn": "some_role",
                    "account_id": "731070500579",
                    "region": "eu-west-1",
                }
                self.check = AwsTopologyCheck(self.CHECK_NAME, cfg, instances=[cfg])
                self.check.run()

                topology = [top.get_snapshot(self.check.check_id)]
                events = aggregator.events

                unique_types = self.unique_topology_types(topology)
                self.assertEqual(len(unique_types), expected_unique_topology_types)

                aws_agent_check_errors = list(filter(lambda x: x['event_type'] == 'aws_agent_check_error', events))
                self.assertEqual(len(aws_agent_check_errors), 1)
        except Exception:
            traceback.print_exc()
            raise
