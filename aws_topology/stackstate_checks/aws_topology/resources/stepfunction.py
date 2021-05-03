from .utils import make_valid_data, create_arn as arn, get_partition_name, set_required_access
from .registry import RegisteredResourceCollector
from collections import namedtuple
import json


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='kinesis', region=region, account_id=account_id, resource_id='stream/' + resource_id)


StateMachineData = namedtuple('StateMachineData', ['state_machine', 'tags'])


class StepFunctionCollector(RegisteredResourceCollector):
    API = "stepfunctions"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.stepfunction"

    @set_required_access('states:ListTagsForResource')
    def collect_tags(self, arn):
        try:
            tags = self.client.list_tags_for_resource(resourceArn=arn).get('tags') or []
        except Exception:  # TODO catch throttle + permission exceptions
            tags = []
        return tags

    @set_required_access('states:DescribeStateMachine')
    def collect_state_machine(self, arn):
        try:
            state_machine = self.client.describe_state_machine(stateMachineArn=arn)
        except Exception:  # TODO catch throttle + permission exceptions
            state_machine = {}
        tags = self.collect_tags(arn)
        return StateMachineData(state_machine=state_machine, tags=tags)

    @set_required_access('states:ListStateMachines')
    def collect_state_machines(self):
        for list_streams_page in self.client.get_paginator('list_state_machines').paginate():
            for state_machine_summary in list_streams_page.get('stateMachines') or []:
                yield self.collect_state_machine(state_machine_summary.get('stateMachineArn'))

    def process_all(self, filter=None):
        for state_machine in self.collect_state_machines():
            self.process_state_machine(state_machine)
        for list_activities_page in self.client.get_paginator('list_activities').paginate():
            for activity_raw in list_activities_page.get('activities') or []:
                activity = make_valid_data(activity_raw)
                self.process_activity(activity)

    @set_required_access('states:DescribeStateMachine')
    def process_state_machine(self, data):
        # generate component
        arn = data.state_machine.get('stateMachineArn')
        output = make_valid_data(data.state_machine)
        print(output)
        if 'definition' in output:
            output.pop('definition')
        self.agent.component(arn, self.COMPONENT_TYPE, output)
        # get definitions
        definition = data.state_machine.get('definition') or "{}"
        self.process_state_machine_relations(arn, definition)

    def process_activity(self, data):
        activity_arn = data.get('activityArn')
        data["Tags"] = self.collect_tags(activity_arn)
        self.agent.component(arn, 'aws.stepfunction.activity', data)

    def process_state_machine_relations(self, arn, definition):
        data = json.loads(definition)
        states = data.get('States')
        start_state = data.get('StartAt')
        if states:
            for state_name, state in states.items():
                self.process_state(arn, state_name, state, start_state == state_name)

    def process_state(self, arn, state_name, state, is_start=False):
        partition = get_partition_name(self.agent.location['Location']['AwsRegion'])
        state_arn = arn + ':state/' + state_name
        if is_start:
            self.agent.relation(arn, state_arn, 'start state', {})
        self.agent.component(state_arn, 'aws.stepfunction.state', state)
        next_state = state.get('Next')
        if next_state:
            next_state_arn = arn + ':state/' + next_state
            self.agent.relation(state_arn, next_state_arn, 'can transition to', {})
        if isinstance(state, dict) and state.get('Type') == 'Choice':
            choices = state.get('Choices') or []
            default_state = state.get('Default')
            if default_state:
                default_state_arn = arn + ':state/' + default_state
                self.agent.relation(state_arn, default_state_arn, 'can transition to (default)', {})
            for choice in choices:
                choice_next = choice.get('Next')
                if choice_next:
                    choice_arn = arn + ':state/' + choice_next
                    self.agent.relation(state_arn, choice_arn, 'can transition to (choice)', {})
        if isinstance(state, dict) and state.get('Type') == 'Map':
            iterator = state.get('Iterator')
            if iterator:
                start_at = iterator.get('StartAt')
                states = iterator.get('States') or {}
                for state_name, state in states.items():
                    self.process_state(state_arn, state_name, state, state_name == start_at)
        if isinstance(state, dict) and state.get('Type') == 'Parallel':
            branches = state.get('Branches') or []
            for branch in branches:
                start_at = branch.get('StartAt')
                states = branch.get('States') or {}
                for state_name, state in states.items():
                    self.process_state(state_arn, state_name, state, state_name == start_at)
        if isinstance(state, dict) and state.get('Type') == 'Task':
            print('JPK ' + state_name + ': ' + state.get('Resource'))
            resource = state.get('Resource') or ''
            parameters = state.get('Parameters') or {}
            if resource.startswith('arn:{}:states:::lambda:'.format(partition)):
                # we need to figure out if it is version/alias (*aliases are components)
                # support function_name, arn, partial arn (with version/alias)
                pass
            if resource.startswith('arn:aws:lambda:'):
                # we need to figure out if it is version/alias (*aliases are components)
                # support function_name, arn, partial arn (with version/alias)
                pass
            start = 'arn:{}:states:::dynamodb:'.format(partition)
            if resource.startswith(start):
                table_name = parameters.get('TableName')
                if table_name:
                    operation = resource[len(start):]
                    table_arn = self.agent.create_arn('AWS::DynamoDB::Table', resource_id=table_name)
                    self.agent.relation(arn, table_arn, 'uses service', {'operation': operation})
            if resource.startswith('arn:{}:states:::states:'.format(partition)):
                sfn_arn = parameters.get('StateMachineArn')
                if sfn_arn:
                    self.agent.relation(arn, sfn_arn, 'uses service', {})  # TODO get the type of action
            if resource.startswith('arn:{}:states:::sns:'.format(partition)):
                # TopicArn (to topic) or TargetArn (to platform, no component yet)
                topic_arn = parameters.get('TopicArn')
                if topic_arn:
                    self.agent.relation(arn, topic_arn, 'uses service', {})  # TODO get the type of action
            if resource.startswith('arn:{}:states:::sqs:'.format(partition)):
                # QueueUrl
                # This can be cross region!! (tested)
                queue_url = parameters.get('QueueUrl')
                if queue_url:
                    queue_arn = queue_url  # TODO convert to ARN
                    self.agent.relation(arn, queue_arn, 'uses service', {})  # TODO get the type of action
            if resource.startswith('arn:{}:states:::ecs:'.format(partition)):
                definition_id = parameters.get('taskDefinition')
                if definition_id:
                    definition_arn = definition_id  # TODO can be full ARN or family:revision
                    self.agent.relation(arn, definition_arn, 'uses service', {})  # TODO get the type of action
                cluster_id = parameters.get('cluster')
                if cluster_id:
                    cluster_arn = cluster_id  # TODO shortname or ARN
                    cluster_arn
                # TODO NetworkConfiguration also has connection to securitygroups AND subnets
            if resource.startswith('arn:{}:states:::apigateway:'.format(partition)):
                api_host = parameters.get('ApiEndpoint')
                # <API ID>.execute-api.<region>.amazonaws.com
                api_method = parameters.get('Method')
                api_path = parameters.get('Path')
                api_stage = parameters.get('Stage')
                api_method
                api_path
                api_stage
                api_host
            # TODO support AWS Batch / AWS Glue (DataBrew) / EMR / EMR on EKS / EKS / CodeBuild
            # TODO decide on (Athena / SageMaker)
