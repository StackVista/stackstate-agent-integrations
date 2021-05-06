from .utils import make_valid_data, create_arn as arn, get_partition_name, set_required_access
from .registry import RegisteredResourceCollector
from collections import namedtuple
import json
from schematics import Model
from schematics.types import StringType
from .sqs import get_queue_name_from_url


def create_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='kinesis', region=region, account_id=account_id, resource_id='stream/' + resource_id)


StateMachineData = namedtuple('StateMachineData', ['state_machine', 'tags'])


class StepFunction(Model):
    stateMachineArn = StringType(required=True)
    definition = StringType(default="{}")


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
        for list_sfn_page in self.client.get_paginator('list_state_machines').paginate():
            for state_machine_summary in list_sfn_page.get('stateMachines') or []:
                yield self.collect_state_machine(state_machine_summary.get('stateMachineArn'))

    def process_all(self, filter=None):
        if not filter or 'stepfunction' in filter:
            for state_machine in self.collect_state_machines():
                self.process_state_machine(state_machine)
        if not filter or 'activities' in filter:
            for list_activities_page in self.client.get_paginator('list_activities').paginate():
                for activity_raw in list_activities_page.get('activities') or []:
                    activity = make_valid_data(activity_raw)
                    self.process_activity(activity)

    @set_required_access('states:DescribeStateMachine')
    def process_state_machine(self, data):
        # generate component
        state_machine = StepFunction(data.state_machine, strict=False)
        output = make_valid_data(data.state_machine)
        if 'definition' in output:
            output.pop('definition')
        output["tags"] = data.tags
        self.agent.component(state_machine.stateMachineArn, self.COMPONENT_TYPE, output)
        self.process_state_machine_relations(state_machine.stateMachineArn, state_machine.definition)

    def process_activity(self, data):
        activity_arn = data.get('activityArn')
        data["tags"] = self.collect_tags(activity_arn)
        self.agent.component(activity_arn, 'aws.stepfunction.activity', data)

    def process_state_machine_relations(self, arn, definition):
        data = json.loads(definition)
        states = data.get('States')
        start_state = data.get('StartAt')
        if states:
            for state_name, state in states.items():
                self.process_state(arn, arn, state_name, state, start_state == state_name)

    def process_state(self, sfn_arn, arn, state_name, state, is_start=False):
        partition = get_partition_name(self.agent.location['Location']['AwsRegion'])
        state_arn = sfn_arn + ':state/' + state_name
        if is_start:
            self.agent.relation(arn, state_arn, 'uses service', {})  # starts state
        state["Name"] = state_name
        next_state = state.get('Next')
        if next_state:
            next_state_arn = sfn_arn + ':state/' + next_state
            self.agent.relation(state_arn, next_state_arn, 'uses service', {})  # can transition to
        if state.get('Type') == 'Choice':
            choices = state.get('Choices') or []
            default_state = state.get('Default')
            if default_state:
                default_state_arn = sfn_arn + ':state/' + default_state
                self.agent.relation(state_arn, default_state_arn, 'uses service', {})  # can transition to (default)
            for choice in choices:
                choice_next = choice.get('Next')
                if choice_next:
                    choice_arn = sfn_arn + ':state/' + choice_next
                    self.agent.relation(state_arn, choice_arn, 'uses service', {})  # can transition to (choice)
        elif state.get('Type') == 'Map':
            iterator = state.get('Iterator')
            if iterator:
                start_at = iterator.get('StartAt')
                states = iterator.get('States') or {}
                for iterator_state_name, iterator_state in states.items():
                    self.process_state(sfn_arn, state_arn, iterator_state_name, iterator_state, iterator_state_name == start_at)
        elif state.get('Type') == 'Parallel':
            branches = state.get('Branches') or []
            for branch in branches:
                start_at = branch.get('StartAt')
                states = branch.get('States') or {}
                for branch_state_name, branch_state in states.items():
                    self.process_state(sfn_arn, state_arn, branch_state_name, branch_state, branch_state_name == start_at)
        elif state.get('Type') == 'Task':
            # TODO sense intrinsics used in any integration parameter -> don't mae relation
            # TODO resource end part is invokation type put it in the state
            resource = state.get('Resource') or ''
            parameters = state.get('Parameters') or {}
            parts = resource.split(":", -1)
            if len(parts) > 6:
                integration_type = ':'.join(parts[6:])
                if integration_type:
                    state["IntegrationSubType"] = integration_type
            if resource.startswith('arn:{}:states:::lambda:'.format(partition)):
                state["IntegrationType"] = "lambda"
                function = parameters.get('FunctionName')
                parts = function.split(':', -1)
                fn_arn = ''
                if len(parts) == 7:
                    fn_arn = ':'.join(parts)
                elif len(parts) == 8 and (parts[7].isdigit() or  parts[7].lower() == '$latest'):
                    fn_arn = ':'.join(parts[0:7])  # versions are not in StackState so omit
                elif len(parts) == 8:
                    fn_arn = ':'.join(parts)
                elif len(parts) >= 3:
                    fn_arn = self.agent.create_arn('AWS::Lambda::Function', ':'.join(parts[2:]))
                if fn_arn:
                    self.agent.relation(state_arn, fn_arn, 'uses service', {})
            elif resource.startswith('arn:aws:lambda:'):
                state["IntegrationType"] = "lambda"
                function = resource
                parts = function.split(':', -1)
                fn_arn = ''
                if len(parts) == 8 and (parts[7].isdigit() or parts[7].lower() == '$latest'):
                    fn_arn = ':'.join(parts[0:7])  # versions are not in StackState so omit
                elif len(parts) == 8:
                    fn_arn = ':'.join(parts)
                elif len(parts) >= 3:
                    fn_arn = self.agent.create_arn('AWS::Lambda::Function', ':'.join(parts[2:]))
                if fn_arn:
                    self.agent.relation(state_arn, fn_arn, 'uses service', {})
            elif resource.startswith('arn:{}:states:::dynamodb:'.format(partition)):
                state["IntegrationType"] = "dynamodb"
                table_name = parameters.get('TableName')
                if table_name:
                    operation = resource[len('arn:{}:states:::dynamodb:'.format(partition)):]
                    table_arn = self.agent.create_arn('AWS::DynamoDB::Table', resource_id=table_name)
                    self.agent.relation(state_arn, table_arn, 'uses service', {'operation': operation})
            elif resource.startswith('arn:{}:states:::states:'.format(partition)):
                state["IntegrationType"] = "stepfunctions"
                sfn_arn = parameters.get('StateMachineArn')
                if sfn_arn:
                    self.agent.relation(state_arn, sfn_arn, 'uses service', {})  # TODO get the type of action
            elif ':activity:' in resource:
                state["IntegrationType"] = "activity"
                self.agent.relation(state_arn, resource, 'uses service', {})
            elif resource.startswith('arn:{}:states:::sns:'.format(partition)):
                state["IntegrationType"] = "sns"
                # TopicArn (to topic) or TargetArn (to platform, no component yet)
                topic_arn = parameters.get('TopicArn')
                if topic_arn:
                    self.agent.relation(state_arn, topic_arn, 'uses service', {})  # TODO get the type of action
            elif resource.startswith('arn:{}:states:::sqs:'.format(partition)):
                state["IntegrationType"] = "sqs"
                queue_url = parameters.get('QueueUrl')
                if queue_url:
                    queue_name = get_queue_name_from_url(queue_url)
                    queue_arn = self.agent.create_arn('AWS::SQS::Queue', queue_name)
                    self.agent.relation(state_arn, queue_arn, 'uses service', {})  # TODO get the type of action
            elif resource.startswith('arn:{}:states:::ecs:'.format(partition)):
                state["IntegrationType"] = "ecs"
                definition_id = parameters.get('TaskDefinition')
                if definition_id:
                    definition_arn = definition_id  # TODO can be full ARN or family:revision
                    self.agent.relation(state_arn, definition_arn, 'uses service', {})  # TODO get the type of action
                cluster_id = parameters.get('Cluster')
                if cluster_id:
                    cluster_arn = cluster_id
                    if not cluster_id.startswith('arn:'):
                        cluster_arn = self.agent.create_arn('AWS::ECS::Cluster', cluster_id)
                    self.agent.relation(state_arn, cluster_arn, 'uses service', {})
                # TODO NetworkConfiguration also has connection to securitygroups AND subnets
            elif resource.startswith('arn:{}:states:::apigateway:'.format(partition)):
                state["IntegrationType"] = "apigateway"
                api_host = parameters.get('ApiEndpoint')
                if api_host and not api_host.startswith('$.'):
                    # api_method = parameters.get('Method')
                    # api_path = parameters.get('Path')
                    api_id = api_host.split('.')[0]
                    api_stage = parameters.get('Stage')
                    if api_stage and not api_stage.startswith('$.'):
                        api_arn = self.agent.create_arn(
                            'AWS::ApiGateway::RestApi',
                            api_id + '/' + api_stage
                        )
                        self.agent.relation(state_arn, api_arn, 'uses service', {})
            # TODO support AWS Batch / AWS Glue (DataBrew) / EMR / EMR on EKS / EKS / CodeBuild
            # TODO decide on (Athena / SageMaker)
        self.agent.component(state_arn, 'aws.stepfunction.state', state)
