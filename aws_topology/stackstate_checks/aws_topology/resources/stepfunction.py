from .utils import client_array_operation, make_valid_data, get_partition_name, set_required_access_v2, with_dimensions
from .registry import RegisteredResourceCollector
from collections import namedtuple
import json
from schematics import Model
from schematics.types import StringType
from six import string_types


"""
This collector works on boto3 SFN (StepFunction) API Calls

Activity => component
create_activity
delete_activity

StateMachine => component
create_state_machine
delete_state_machine
update_state_machine

Tags
tag_resource
untag_resource

Events (also in cloudtrail)
send_task_failure
send_task_heartbeat
send_task_success
start_execution
start_sync_execution
stop_execution


Reading from the API
list_activities
    describe_activity
    list_tags_for_resource

list_state_machines()
    describe_state_machine
    list_tags_for_resource

Unused ReadOnly
describe_execution
describe_state_machine_for_execution
get_activity_task
get_execution_history
"""


StateMachineData = namedtuple("StateMachineData", ["state_machine", "tags"])
ActivityData = namedtuple("ActivityData", ["activity", "tags"])


class StepFunction(Model):
    stateMachineArn = StringType(required=True)
    definition = StringType(default="{}")
    roleArn = StringType()


class Activity(Model):
    activityArn = StringType(required=True)
    name = StringType()


class StepFunctionCollector(RegisteredResourceCollector):
    API = "stepfunctions"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.stepfunction"

    @set_required_access_v2("states:ListTagsForResource")
    def collect_tags(self, arn):
        return self.client.list_tags_for_resource(resourceArn=arn).get("tags")

    @set_required_access_v2("states:DescribeStateMachine")
    def collect_state_machine_description(self, arn):
        return self.client.describe_state_machine(stateMachineArn=arn)

    def collect_state_machine(self, summary):
        arn = summary.get("stateMachineArn")
        state_machine = self.collect_state_machine_description(arn) or {"stateMachineArn": arn}
        tags = self.collect_tags(arn) or []
        return StateMachineData(state_machine=state_machine, tags=tags)

    def collect_state_machines(self):
        for state_machine_data in client_array_operation(self.client, "list_state_machines", "stateMachines"):
            yield self.collect_state_machine(state_machine_data)

    def collect_activity(self, data):
        activity_arn = data.get("activityArn")
        tags = self.collect_tags(activity_arn)
        return ActivityData(activity=data, tags=tags)

    def collect_activities(self):
        for activity in [
            self.collect_activity(activity)
            for activity in client_array_operation(self.client, "list_activities", "activities")
        ]:
            yield activity

    def process_all(self, filter=None):
        if not filter or "stepfunctions" in filter:
            self.process_state_machines()
        if not filter or "activities" in filter:
            self.process_activities()

    @set_required_access_v2("states:ListActivities")
    def process_activities(self):
        for activity in self.collect_activities():
            self.process_activity(activity)

    @set_required_access_v2("states:ListStateMachines")
    def process_state_machines(self):
        for state_machine in self.collect_state_machines():
            self.process_state_machine(state_machine)

    def process_activity(self, data):
        output = make_valid_data(data.activity)
        activity = Activity(data.activity, strict=False)
        activity.validate()
        output["tags"] = data.tags
        output.update(
            with_dimensions(
                [{"key": "ActivityArn", "value": activity.activityArn}]
            )
        )
        self.emit_component(activity.activityArn, ".".join([self.COMPONENT_TYPE, "activity"]), output)

    def process_one_state_machine(self, arn):
        self.process_state_machine(self.collect_state_machine({"stateMachineArn": arn}))

    def process_one_activity(self, arn):
        self.process_activity(self.collect_activity({"activityArn": arn}))

    def process_deletion(self, arn):
        self.agent.delete(arn)

    def process_one_resource(self, arn):
        if isinstance(arn, string_types):
            parts = arn.split(":")
            if len(parts) >= 6:
                if parts[5] == "activity":
                    self.process_one_activity(arn)
                elif parts[5] == "stateMachine":
                    self.process_one_activity(arn)

    def process_state_machine(self, data):
        # generate component
        state_machine = StepFunction(data.state_machine, strict=False)
        output = make_valid_data(data.state_machine)
        if "definition" in output:
            output.pop("definition")
        output["tags"] = data.tags
        output.update(
            with_dimensions(
                [{"key": "StateMachineArn", "value": state_machine.stateMachineArn}]
            )
        )
        self.emit_component(state_machine.stateMachineArn, ".".join([self.COMPONENT_TYPE, "statemachine"]), output)
        if state_machine.roleArn:
            self.emit_relation(state_machine.stateMachineArn, state_machine.roleArn, "uses-service", {})
        self.process_state_machine_relations(state_machine.stateMachineArn, state_machine.definition)

    def process_state_machine_relations(self, arn, definition):
        data = json.loads(definition)
        states = data.get("States")
        start_state = data.get("StartAt")
        if states:
            for state_name, state in states.items():
                self.process_state(arn, arn, state_name, state, start_state == state_name)

    def process_state(self, sfn_arn, arn, state_name, state, is_start=False):
        state_arn = sfn_arn + ":state/" + state_name
        if is_start:
            self.emit_relation(arn, state_arn, "uses-service", {})  # starts state
        state["Name"] = state_name
        next_state = state.get("Next")
        if next_state:
            next_state_arn = sfn_arn + ":state/" + next_state
            self.emit_relation(state_arn, next_state_arn, "uses-service", {})  # can transition to
        state_type = state.get("Type")
        if state_type == "Choice":
            self.process_choice_state(sfn_arn, state_arn, state.get("Choices"), state.get("Default"))
        elif state_type == "Map":
            self.process_map_state(sfn_arn, state_arn, state.get("Iterator"))
        elif state_type == "Parallel":
            self.process_parallel_state(sfn_arn, state_arn, state.get("Branches"))
        elif state_type == "Task":
            self.process_task_state(state_arn, state)
        self.emit_component(state_arn, "state", state)

    def process_choice_state(self, sfn_arn, state_arn, choices, default_state):
        choices = choices or []
        if default_state:
            default_state_arn = sfn_arn + ":state/" + default_state
            self.emit_relation(state_arn, default_state_arn, "uses-service", {})  # can transition to (default)
        for choice in choices:
            choice_next = choice.get("Next")
            if choice_next:
                choice_arn = sfn_arn + ":state/" + choice_next
                self.emit_relation(state_arn, choice_arn, "uses-service", {})  # can transition to (choice)

    def process_map_state(self, sfn_arn, state_arn, iterator):
        iterator = iterator or {}
        if iterator:
            start_at = iterator.get("StartAt")
            states = iterator.get("States", {})
            for iterator_state_name, iterator_state in states.items():
                self.process_state(
                    sfn_arn, state_arn, iterator_state_name, iterator_state, iterator_state_name == start_at
                )

    def process_parallel_state(self, sfn_arn, state_arn, branches):
        branches = branches or []
        for branch in branches:
            start_at = branch.get("StartAt")
            states = branch.get("States", {})
            for branch_state_name, branch_state in states.items():
                self.process_state(sfn_arn, state_arn, branch_state_name, branch_state, branch_state_name == start_at)

    def get_function_reference(self, reference):
        fn_arn = ""
        if isinstance(reference, string_types):
            parts = reference.split(":", -1)
            if isinstance(parts, list):
                if len(parts) >= 7 and len(parts) <= 8:
                    # example: arn:aws:lambda:us-east-2:123456789012:function:name
                    # example: arn:aws:lambda:us-east-2:123456789012:function:name:12
                    # example: arn:aws:lambda:us-east-2:123456789012:function:name:$latest
                    # example: arn:aws:lambda:us-east-2:123456789012:function:name:alias
                    if len(parts) == 8 and parts[-1].isdigit() or parts[-1].lower() == "$latest":
                        parts.pop(-1)
                    fn_arn = ":".join(parts)
                elif len(parts) >= 1 and len(parts) <= 4:
                    # example: name
                    # example: name:12
                    # example: name:$latest
                    # example: name:alias
                    # example: 123456789012:function:name         (partial name)
                    # example: 123456789012:function:name:12      (partial name+version)
                    # example: 123456789012:function:name:$latest (partial name+latest)
                    # example: 123456789012:function:name:alias   (partial name+alias)
                    if parts[-1].isdigit() or parts[-1].lower() == "$latest":
                        parts.pop(-1)
                    # now skip accountid and 'function' (when there)
                    start = 0
                    if len(parts) > 2:
                        start = 2
                    fn_arn = self.agent.create_arn("AWS::Lambda::Function", self.location_info, ":".join(parts[start:]))
        if not fn_arn:
            self.agent.warning("Could not make lambda relation of {}".format(reference))
        return fn_arn

    def process_task_state(self, state_arn, state):
        # TODO sense intrinsics used in any integration parameter -> don't make relation
        # TODO resource end part is invokation type put it in the state
        # TODO support AWS Batch / AWS Glue (DataBrew) / EMR / EMR on EKS / EKS / CodeBuild
        # TODO decide on (Athena / SageMaker)
        partition = get_partition_name(self.location_info.Location.AwsRegion)
        resource = state.get("Resource") or ""
        parameters = state.get("Parameters", {})
        parts = resource.split(":", -1)
        if len(parts) > 6:
            integration_type = ":".join(parts[6:])
            if integration_type:
                state["IntegrationSubType"] = integration_type
        if resource.startswith("arn:{}:states:::lambda:".format(partition)):
            state["IntegrationType"] = "lambda"
            fn_arn = self.get_function_reference(parameters.get("FunctionName"))
            if fn_arn:
                self.emit_relation(state_arn, fn_arn, "uses-service", {})
        elif resource.startswith("arn:{}:lambda:".format(partition)):
            state["IntegrationType"] = "lambda"
            fn_arn = self.get_function_reference(resource)
            if fn_arn:
                self.emit_relation(state_arn, fn_arn, "uses-service", {})
        elif resource.startswith("arn:{}:states:::dynamodb:".format(partition)):
            state["IntegrationType"] = "dynamodb"
            table_name = parameters.get("TableName")
            if table_name:
                operation = resource[len("arn:{}:states:::dynamodb:".format(partition)) :]
                table_arn = self.agent.create_arn("AWS::DynamoDB::Table", self.location_info, resource_id=table_name)
                self.emit_relation(state_arn, table_arn, "uses-service", {"operation": operation})
        elif resource.startswith("arn:{}:states:::states:".format(partition)):
            state["IntegrationType"] = "stepfunctions"
            sfn_arn = parameters.get("StateMachineArn")
            if sfn_arn:
                self.emit_relation(state_arn, sfn_arn, "uses-service", {})  # TODO get the type of action
        elif ":activity:" in resource:
            state["IntegrationType"] = "activity"
            self.emit_relation(state_arn, resource, "uses-service", {})
        elif resource.startswith("arn:{}:states:::sns:".format(partition)):
            # TODO TopicArn (to topic) or TargetArn (to platform, no component yet)
            state["IntegrationType"] = "sns"
            topic_arn = parameters.get("TopicArn")
            if topic_arn:
                self.emit_relation(state_arn, topic_arn, "uses-service", {})  # TODO get the type of action
        elif resource.startswith("arn:{}:states:::sqs:".format(partition)):
            state["IntegrationType"] = "sqs"
            queue_url = parameters.get("QueueUrl")
            if queue_url:
                queue_arn = self.agent.create_arn("AWS::SQS::Queue", self.location_info, queue_url)
                self.emit_relation(state_arn, queue_arn, "uses-service", {})  # TODO get the type of action
        elif resource.startswith("arn:{}:states:::ecs:".format(partition)):
            # TODO can be full ARN or family:revision
            # TODO NetworkConfiguration also has connection to securitygroups AND subnets
            state["IntegrationType"] = "ecs"
            definition_id = parameters.get("TaskDefinition")
            if definition_id:
                definition_arn = definition_id
                self.emit_relation(state_arn, definition_arn, "uses-service", {})  # TODO get the type of action
            cluster_id = parameters.get("Cluster")
            if cluster_id:
                cluster_arn = cluster_id
                if not cluster_id.startswith("arn:"):
                    cluster_arn = self.agent.create_arn("AWS::ECS::Cluster", self.location_info, cluster_id)
                self.emit_relation(state_arn, cluster_arn, "uses-service", {})
        elif resource.startswith("arn:{}:states:::apigateway:".format(partition)):
            state["IntegrationType"] = "apigateway"
            api_host = parameters.get("ApiEndpoint")
            if api_host and not api_host.startswith("$."):
                # TODO connection currently made to stage and not resource/method
                # api_method = parameters.get('Method')
                # api_path = parameters.get('Path')
                api_id = api_host.split(".")[0]
                api_stage = parameters.get("Stage")
                if api_stage and not api_stage.startswith("$."):
                    api_arn = self.agent.create_arn(
                        "AWS::ApiGateway::RestApi", self.location_info, api_id + "/" + api_stage
                    )
                    self.emit_relation(state_arn, api_arn, "uses-service", {})

    EVENT_SOURCE = "states.amazonaws.com"
    CLOUDTRAIL_EVENTS = [
        {"event_name": "CreateActivity", "path": "responseElements.activityArn", "processor": process_one_activity},
        {"event_name": "DeleteActivity", "path": "requestParameters.activityArn", "processor": process_deletion},
        {
            "event_name": "CreateStateMachine",
            "path": "responseElements.stateMachineArn",
            "processor": process_one_state_machine,
        },
        {
            "event_name": "DeleteStateMachine",
            "path": "requestParameters.stateMachineArn",
            "processor": process_deletion,
        },
        {"event_name": "TagResource", "path": "requestParameters.resourceArn", "processor": process_one_resource},
        {"event_name": "UntagResource", "path": "requestParameters.resourceArn", "processor": process_one_resource},
        {
            "event_name": "UpdateStateMachine",
            "path": "requestParameters.stateMachineArn",
            "processor": process_one_state_machine,
        },
    ]
