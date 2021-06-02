import unittest
import os
import json
from mock import patch
import datetime
from stackstate_checks.base.stubs import topology as top, aggregator
from stackstate_checks.aws_topology import AwsTopologyCheck, InitConfig
from stackstate_checks.base import AgentCheck


def relative_path(path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, path)


def resource(path):
    with open(relative_path(path)) as f:
        x = json.load(f)
    return x


def set_event(value):
    def inner(func):
        func.event = value
        return func

    return inner


def mock_event(event_name):

    def mock_boto_calls(operation_name, kwarg=None):
        if operation_name == "AssumeRole":
            return {"Credentials": {"AccessKeyId": "KEY_ID", "SecretAccessKey": "ACCESS_KEY", "SessionToken": "TOKEN"}}
        elif operation_name == 'LookupEvents':
            res = resource("json/cloudtrail/" + event_name + ".json")
            res['eventTime'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            msg = {
                "Events": [
                    {
                        "CloudTrailEvent": json.dumps(res)
                    }
                ]
            }
            return msg
        elif operation_name == 'GetQueueAttributes':
            return resource("json/cloudtrail/get_queue_attributes.json")
        elif operation_name == 'DescribeDeliveryStream':
            return resource("json/cloudtrail/describe_delivery_stream.json")
        elif operation_name == 'DescribeStreamSummary':
            return resource("json/cloudtrail/describe_stream_summary.json")
        elif operation_name == 'DescribeTable':
            return resource("json/cloudtrail/describe_table.json")
        elif operation_name == 'DescribeAutoScalingGroups':
            return resource("json/cloudtrail/describe_autoscaling_group.json")
        elif operation_name == 'DescribeClusters':
            return resource("json/cloudtrail/redshift_describe_clusters.json")
        elif operation_name == 'DescribeDBClusters':
            return resource("json/cloudtrail/describe_rds_clusters.json")
        elif operation_name == 'DescribeDBInstances':
            return resource("json/cloudtrail/describe_rds_instances.json")
        elif (
            operation_name == 'ListQueueTags'
            or operation_name == 'ListTagsForDeliveryStream'
            or operation_name == 'ListTagsForStream'
            or operation_name == 'ListTagsOfResource'
            or operation_name == 'ListTagsForResource'
            or operation_name == 'ListSubscriptionsByTopic'
            or operation_name == 'GetBucketLocation'
            or operation_name == 'GetBucketTagging'
            or operation_name == 'GetBucketNotificationConfiguration'
        ):
            return {}
        raise ValueError("Unknown operation name", operation_name)

    return mock_boto_calls


class TestCloudtrail(unittest.TestCase):

    CHECK_NAME = "aws_topology"
    SERVICE_CHECK_NAME = "aws_topology"

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
            "regions": ["eu-west-1"],
        }
        instance.update({"apis_to_run": []})

        self.check = AwsTopologyCheck(self.CHECK_NAME, InitConfig(init_config), [instance])
        self.mock_object.side_effect = mock_event(method.event)

    def tearDown(self):
        self.patcher.stop()

    def assert_executed_ok(self):
        service_checks = aggregator.service_checks(self.check.SERVICE_CHECK_EXECUTE_NAME)
        self.assertGreater(len(service_checks), 0)
        self.assertEqual(service_checks[0].status, AgentCheck.OK, service_checks[0].message)

    @set_event('sqs_create_queue')
    def test_process_sqs_create(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/CreatedQueueName',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_set_queue_attributes')
    def test_process_sqs_update_attributes(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/UpdatedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_tag_queue')
    def test_process_sqs_tag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/TaggedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_untag_queue')
    def test_process_sqs_untag_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'https://sqs.eu-west-1.amazonaws.com/123456789012/UntaggedQueue',
            topology[0]["components"][0]["data"]["QueueUrl"]
        )

    @set_event('sqs_delete_queue')
    def test_process_sqs_delete_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:sqs:eu-west-1:123456789012:DeletedQueue', self.check.delete_ids)

    @set_event('sqs_purge_queue')
    def test_process_sqs_purge_queue(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertEqual(len(self.check.delete_ids), 0)
        # TODO test that an event is emitted

    @set_event('firehose_create_stream')
    def test_process_firehose_create_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'dnv-sam-seed-button-clicked-firehose',
            topology[0]["components"][0]["data"]["DeliveryStreamDescription"]["DeliveryStreamName"]
        )

    @set_event('firehose_delete_stream')
    def test_process_firehose_delete_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:firehose:eu-west-1:731070500579:deliverystream/AnotherDelivery', self.check.delete_ids)

    @set_event('firehose_start_encryption')
    def test_process_firehose_start_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1',
            topology[0]["components"][0]["id"]
        )

    @set_event('firehose_stop_encryption')
    def test_process_firehose_stop_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1',
            topology[0]["components"][0]["id"]
        )

    @set_event('firehose_tag_stream')
    def test_process_firehose_tag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1',
            topology[0]["components"][0]["id"]
        )

    @set_event('firehose_untag_stream')
    def test_process_firehose_untag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1',
            topology[0]["components"][0]["id"]
        )

    @set_event('firehose_update_destination')
    def test_process_firehose_update_destination(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:firehose:eu-west-1:731070500579:deliverystream/firehose_1',
            topology[0]["components"][0]["id"]
        )

    @set_event('kinesis_create_stream')
    def test_process_kinesis_create_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_delete_stream')
    def test_process_kinesis_delete_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:kinesis:eu-west-1:731070500579:stream/TestStream', self.check.delete_ids)

    @set_event('kinesis_tag_stream')
    def test_process_kinesis_tag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_untag_stream')
    def test_process_kinesis_untag_stream(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_increase_retention')
    def test_process_kinesis_increase_retention(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_decrease_retention')
    def test_process_kinesis_decrease_retention(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_enable_enh_monitoring')
    def test_process_kinesis_enable_enh_monitoring(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_disable_enh_monitoring')
    def test_process_kinesis_disable_enh_monitoring(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_start_encryption')
    def test_process_kinesis_start_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_stop_encryption')
    def test_process_kinesis_stop_encryption(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('kinesis_update_shard_count')
    def test_process_update_shard_count(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stream_1',
            topology[0]["components"][0]["data"]["StreamDescriptionSummary"]["StreamName"]
        )

    @set_event('dynamodb_create_table')
    def test_process_dynamodb_create_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_1',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_event('dynamodb_delete_table')
    def test_process_dynamodb_delete_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:dynamodb:eu-west-1:731070500579:table/JpkTest', self.check.delete_ids)

    @set_event('dynamodb_tag_table')
    def test_process_dynamodb_tag_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_1',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_event('dynamodb_untag_table')
    def test_process_dynamodb_untag_table(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:dynamodb:eu-west-1:731070500579:table/table_1',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_event('s3_create_bucket')
    def test_process_s3_create_bucket(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'stackstate-logs-123456789012',
            topology[0]["components"][0]["data"]["Name"]
        )

    @set_event('s3_delete_bucket')
    def test_process_s3_delete_bucket(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:s3:::stackstate-logs-123456789012', self.check.delete_ids)

    @set_event('autoscaling_create_autoscaling_group')
    def test_process_create_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )

    @set_event('autoscaling_delete_autoscaling_group')
    def test_process_autoscaling_delete_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'elvin-stackstate-tests-main-account-main-region-EcsAutoScalingGroup-VVC5WIJ3AI3K',
            self.check.delete_ids
        )

    @set_event('autoscaling_create_or_update_tags')
    def test_process_create_or_update_tags(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )

    @set_event('autoscaling_update_autoscaling_group')
    def test_process_autoscaling_update_autoscaling_group(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM',
            topology[0]["components"][0]["data"]["AutoScalingGroupName"]
        )

    @set_event('sns_create_topic')
    def test_process_sns_create_topic(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:sns:eu-west-1:123456789012:MyFirstSNS',
            topology[0]["components"][0]["id"]
        )

    @set_event('sns_delete_topic')
    def test_process_sns_delete_topic(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn(
            'arn:aws:sns:eu-west-1:123456789012:sam-integ-stack-basic-application-' +
            'sar-location-with-intrinsics-dqaojpvdfwji-MySns-NSB98RV5ST8D', self.check.delete_ids
        )

    @set_event('redshift_create_cluster')
    def test_process_redshift_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'mycluster',
            topology[0]["components"][0]["id"]
        )

    @set_event('redshift_delete_cluster')
    def test_process_redshift_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('my-dw-instance', self.check.delete_ids)

    @set_event('rds_create_cluster')
    def test_process_rds_create_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:rds:eu-west-1:731070500579:cluster:productiondatabasecluster',
            topology[0]["components"][0]["id"]
        )

    @set_event('rds_delete_cluster')
    def test_process_rds_delete_cluster(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:rds:eu-west-1:731070500579:cluster:hithere', self.check.delete_ids)

    @set_event('rds_create_instance')
    def test_process_rds_create_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 1)
        self.assertEqual(
            'arn:aws:rds:eu-west-1:731070500579:db:productiondatabase',
            topology[0]["components"][0]["id"]
        )

    @set_event('rds_delete_instance')
    def test_process_rds_delete_instance(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()
        self.assertEqual(len(topology[0]["components"]), 0)
        self.assertIn('arn:aws:rds:eu-west-1:731070500579:db:hithere', self.check.delete_ids)
