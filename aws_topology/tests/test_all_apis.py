from stackstate_checks.base.stubs import topology as top, aggregator
from .conftest import BaseApiTest
from mock import patch
from parameterized import parameterized
from stackstate_checks.aws_topology.resources import ResourceRegistry
from copy import deepcopy


def dont_send_parked_relations(self):
    pass


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


class TestAllApis(BaseApiTest):

    def get_api(self):
        return None

    def get_account_id(self):
        return "731070500579"

    def get_region(self):
        return ['global', 'eu-west-1']

    @patch(
        "stackstate_checks.aws_topology.aws_topology.AgentProxy.finalize_account_topology",
        dont_send_parked_relations
    )
    def test_process_cloudformation(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        components = topology[0]["components"]
        relations = topology[0]["relations"]

        stacks = list(filter(lambda x: x["type"] == "aws.cloudformation", components))
        self.assertEqual(len(stacks), 2)

        # total relations should be 14 + 1
        relations = list(
            filter(
                lambda x: x["type"] == "has resource" and x["source_id"].startswith("arn:aws:cloudformation"),
                topology[0]["relations"],
            )
        )

        source_id = relations[0]["source_id"]

        # assert for lambda function relation
        top.assert_relation(
            relations,
            source_id,
            "arn:aws:lambda:eu-west-1:731070500579:function:com-stackstate-prod-sam-seed-PutHello-1LUD3ESBOR6EY",
            "has resource"
        )
        # assert for kinesis stream relation
        top.assert_relation(
            relations, source_id, "arn:aws:kinesis:eu-west-1:731070500579:stream/stream_1",
            "has resource"
        )
        # assert for s3 bucket relation
        top.assert_relation(
            relations, source_id, "arn:aws:s3:::stackstate.com",
            "has resource"
        )
        # assert for api_stage relation
        top.assert_relation(
            relations, source_id, "arn:aws:execute-api:eu-west-1:731070500579:api_1",
            "has resource"
        )
        # assert for loadbalancer relation
        top.assert_relation(
            relations, source_id,
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:loadbalancer/app/myfirstloadbalancer/90dd512583d2d7e9",
            "has resource"
        )
        # assert for target group relation
        top.assert_relation(
            relations, source_id,
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:targetgroup/myfirsttargetgroup/28ddec997ec55d21",
            "has resource"
        )
        # assert for autoscaling group relation
        top.assert_relation(
            relations, source_id,
            "awseb-e-gwhbyckyjq-stack-AWSEBAutoScalingGroup-35ZMDUKHPCUM",
            "has resource"
        )
        # assert for elb classic loadbalancer  relation
        top.assert_relation(
            relations, source_id,
            "arn:aws:elasticloadbalancing:eu-west-1:731070500579:loadbalancer/classic-loadbalancer-1",
            "has resource"
        )
        # assert for rds relation
        top.assert_relation(
            relations, source_id, "arn:aws:rds:eu-west-1:731070500579:db:productiondatabase",
            "has resource"
        )
        # assert for sns topic relation
        top.assert_relation(
            relations, source_id, "arn:aws:sns:eu-west-1:731070500579:my-topic-3",
            "has resource"
        )
        # assert for sqs queue relation
        top.assert_relation(
            relations, source_id, "arn:aws:sqs:eu-west-1:731070500579:STS_stackpack_test",
            "has resource"
        )
        # assert for dynamodb table relation
        top.assert_relation(
            relations, source_id, "arn:aws:dynamodb:eu-west-1:731070500579:table/table_3",
            "has resource"
        )
        # assert for ecs cluster relation
        top.assert_relation(
            relations, source_id, "arn:aws:ecs:eu-west-1:731070500579:cluster/StackState-ECS-Cluster",
            "has resource"
        )
        # assert for ec2 instance relation
        top.assert_relation(
            relations, source_id, "i-0aac5bab082561475",
            "has resource"
        )

        top.assert_all_checked(components, relations, unchecked_components=133)

    def unique_topology_types(self, topology):
        return set([c["type"] for ti in topology for c in ti["components"]])

    total_unique_types = 36

    def test_check_unique_type(self):
        self.check.run()
        topology = [top.get_snapshot(self.check.check_id)]
        self.assertEqual(len(topology), 1)
        self.assert_executed_ok()

        events = aggregator.events

        aws_agent_check_errors = list(filter(lambda x: x["event_type"] == "aws_agent_check_error", events))
        self.assertEqual(len(aws_agent_check_errors), 0)

        unique_types = self.unique_topology_types(topology)
        self.assertEqual(len(unique_types), self.total_unique_types)

    @parameterized.expand([
        ('ec2|instances vpcs security_groups', total_unique_types-1),  # - vpn_gateway
        ('ec2|instances vpn_gateways security_groups', total_unique_types-2),  # -vpc -subnet
        ('autoscaling', 35),  # - autoscaling group
        ('apigateway', 31),  # - api - stage - resource - method - integration (dummy)
        ('firehose', 35),  # - stream

        ('kinesis', 35),  # - stream
        ('dynamodb', 34),  # - table - stream
        ('lambda|mappings', 34),  # - lambda - alias
        ('lambda|functions', 36),  # only relations (mappings)
        ('sqs', 35),  # - queue

        ('sns', 35),  # - topic
        ('redshift', 35),  # - cluster
        ('s3', 35),  # - bucket
        ('rds', 34),  # - cluster - database
        ('elbv2', 33),  # - loadbalancer, - target_group - targetgroup instance

        ('elb', 35),  # - loadbalancer
        ('ec2|vpcs vpn_gateways security_groups', 35),  # - instance
        ('ecs', 33),  # - task / cluster / service
        ('route53domains', 35),  # -domain
        ('route53', 35),  # -hostedzone
        ('cloudformation', 35),  # -stack
        ('ec2|instances vpcs vpn_gateways', 35),  # - security_group
        ('stepfunctions|stepfunctions', 35),  # - activity
        ('stepfunctions|activities', 34),  # - machine - state
    ])
    def test_check_error_handling(self, check_name, expected_unique_topology_types):
        with patch(
            'stackstate_checks.aws_topology.resources.ResourceRegistry.get_registry',
            wraps=get_wrapper(check_name)
        ):
            top.reset()
            self.check.run()
            topology = [top.get_snapshot(self.check.check_id)]
            self.assertEqual(len(topology), 1)
            events = aggregator.events

            unique_types = self.unique_topology_types(topology)
            self.assertEqual(len(unique_types), expected_unique_topology_types)
            # TODO I can't return an error when running an API partly (error handling is WIP)
            if "|" not in check_name:
                aws_agent_check_errors = list(filter(lambda x: x['event_type'] == 'aws_agent_check_error', events))
                self.assertEqual(len(aws_agent_check_errors), 1)
