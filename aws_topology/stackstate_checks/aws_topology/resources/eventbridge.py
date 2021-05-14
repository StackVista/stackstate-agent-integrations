from .utils import set_required_access_v2, client_array_operation, make_valid_data, \
    create_arn as arn, CloudTrailEventBase
from .registry import RegisteredResourceCollector
from collections import namedtuple
from schematics import Model
from schematics.types import StringType, ModelType

"""
Cloudtrail events: (phase capturing messages)
* tag_resource()
* untag_resource()
* create_event_bus()
* delete_event_bus()
* put_permission()
* remove_permission()
*  delete_rule()
* disable_rule()
* enable_rule()
* put_rule()
* put_targets()
* remove_targets()
* create_api_destination()
* delete_api_destination()
* update_api_destination()
* create_connection()
* deauthorize_connection()
* delete_connection()
* update_connection()
  activate_event_source()
  deactivate_event_source()
* create_archive()
* delete_archive()
* update_archive()
* cancel_replay()
* start_replay()

Rule metrics:
DeadLetterInvocations           Count
FailedInvocations               Count
Invocations                     Count
InvocationsFailedToBeSentToDlq  Count
InvocationsSentToDlq            Count
ThrottledRules                  Count
TriggeredRules                  Count
MatchedEvents                   Count

Across rules:
FailedInvocations
Invocations
MatchedEvents
TriggeredRules

Todo:
- distinguish between schedule rules and event pattern rules! (maybe different component?)
- discover eventbridge vpc interfaces?

"""


def create_event_bus_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='events', region=region, account_id=account_id, resource_id='event-bus/' + resource_id)


def create_rule_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='events', region=region, account_id=account_id, resource_id='rule/' + resource_id)


def create_archive_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='events', region=region, account_id=account_id, resource_id='archive/' + resource_id)


def create_replay_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='events', region=region, account_id=account_id, resource_id='replay/' + resource_id)


class ReplayAction(CloudTrailEventBase):
    class ResponseElements(Model):
        replayName = StringType(required=True)

    responseElements = ModelType(ResponseElements, required=True)

    def get_operation_type(self):
        return 'E'


EventBusData = namedtuple('EventBusData', ['summary', 'description', 'tags', 'rules'])
RuleData = namedtuple('RuleData', ['summary', 'description', 'tags', 'targets'])
ConnectionData = namedtuple('ConnectionData', ['summary', 'description'])
ApiDestinationData = namedtuple('ApiDestinationData', ['summary', 'description'])
ArchiveData = namedtuple('ArchiveData', ['summary', 'description'])
ReplayData = namedtuple('ReplayData', ['summary', 'description'])


class EventBusDescription(Model):
    Arn = StringType(required=True)


class RuleDescription(Model):
    Arn = StringType(required=True)
    State = StringType(required=True)
    RoleArn = StringType()


class RuleTarget(Model):
    Id = StringType(required=True)
    Arn = StringType(required=True)
    RoleArn = StringType()


class ApiConnection(Model):
    ConnectionArn = StringType(required=True)
    ConnectionState = StringType(required=True)
    SecretArn = StringType()


class ApiDestination(Model):
    ApiDestinationArn = StringType(required=True)
    ApiDestinationState = StringType(required=True)
    ConnectionArn = StringType(required=True)


class Archive(Model):
    ArchiveArn = StringType(required=True)
    ArchiveName = StringType(default="UNKNOWN")
    EventSourceArn = StringType()
    State = StringType(default="UNKNOWN")


class ReplayDestination(Model):
    Arn = StringType(required=True)


class Replay(Model):
    ReplayArn = StringType(required=True)
    ReplayName = StringType(default="UNKNOWN")
    State = StringType(default="UNKNOWN")
    EventSourceArn = StringType()
    Destination = ModelType(ReplayDestination)


class EventSource(Model):
    Arn = StringType(required=True)
    Name = StringType(required=True)
    State = StringType(required=True)


class EventBridgeProcessor(RegisteredResourceCollector):
    API = "events"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.events.bus"
    CLOUDFORMATION_TYPE = 'AWS::Events::EventBus'

    @set_required_access_v2('events:ListTagsForResource', ignore=True)
    def collect_tags(self, arn):
        return self.client.list_tags_for_resource(ResourceARN=arn).get('Tags')

    @set_required_access_v2('events:DescribeEventBus', ignore=True)
    def collect_event_bus_description(self, arn):
        return self.client.describe_event_bus(Name=arn)

    def collect_event_bus(self, event_bus):
        arn = event_bus.get('Arn')
        name = event_bus.get('Name')
        description = self.collect_event_bus_description(arn) or {"Arn": arn}
        tags = self.collect_tags(arn) or []
        rules = self.collect_rules(name) or []
        return EventBusData(summary=event_bus, description=description, tags=tags, rules=rules)

    def collect_event_buses(self):
        for event_bus in [
                self.collect_event_bus(event_bus_summary) for event_bus_summary in client_array_operation(
                    self.client,
                    'list_event_buses',
                    'EventBuses'
                )
        ]:
            yield event_bus

    @set_required_access_v2('events:DescribeRule', ignore=True)
    def collect_rule_description(self, bus_name, rule_name):
        return self.client.describe_rule(EventBusName=bus_name, Name=rule_name)

    def collect_rule(self, bus_name, rule_summary):
        arn = rule_summary.get('Arn')
        name = rule_summary.get('Name')
        tags = self.collect_tags(arn) or []
        description = self.collect_rule_description(bus_name, name) or { "Arn": arn, "State": "UNKNOWN" }
        targets = self.collect_targets(bus_name, name) or []
        return RuleData(summary=rule_summary, tags=tags, description=description, targets=targets)

    @set_required_access_v2('events:ListRules', ignore=True)
    def collect_rules(self, bus_name):
        return [
            self.collect_rule(bus_name, rule_summary) for rule_summary in client_array_operation(
                self.client,
                'list_rules',
                'Rules',
                EventBusName=bus_name
            )
        ]

    def collect_target(self, target):
        return target

    @set_required_access_v2('events:ListTargetsByRule', ignore=True)
    def collect_targets(self, bus_name, rule_name):
        return [
                self.collect_target(target) for target in client_array_operation(
                    self.client,
                    'list_targets_by_rule',
                    'Targets',
                    EventBusName=bus_name,
                    Rule=rule_name
                )
        ]

    def collect_api_destination_description(self, name):
        try:
            return self.client.describe_api_destination(Name=name)
        except Exception:
            return {}

    def collect_api_destination(self, summary):
        name = summary.get('Name')
        description = self.collect_api_destination_description(name)
        return ApiDestinationData(summary=summary, description=description)

    def collect_api_destinations(self):
        for destination in [
                self.collect_api_destination(destination) for destination in client_array_operation(
                    self.client,
                    'list_api_destinations',
                    'ApiDestinations'
                )
        ]:
            yield destination

    def collect_connection_description(self, connection_name):
        try:
            return self.client.describe_connection(Name=connection_name)
        except Exception:
            return {}

    def collect_connection(self, connection):
        name = connection.get('Name')
        description = self.collect_connection_description(name)
        return ConnectionData(summary=connection, description=description)

    def collect_connections(self):
        for connection in [
                self.collect_connection(connection) for connection in client_array_operation(
                    self.client,
                    'list_connections',
                    'Connections'
                )
        ]:
            yield connection

    @set_required_access_v2('events:DescribeArchive', ignore=True)
    def collect_archive_description(self, name):
        return self.client.describe_archive(ArchiveName=name)

    def collect_archive(self, archive):
        name = archive.get('ArchiveName')
        archive.update({
            "ArchiveArn": self.agent.create_arn(
                "AWS::Events::Archive",
                self.location_info,
                name
            )
        })
        description = self.collect_archive_description(name) or archive
        return ArchiveData(summary=archive, description=description)

    def collect_archives(self):
        for archive in [
                self.collect_archive(archive) for archive in client_array_operation(
                    self.client,
                    'list_archives',
                    'Archives'
                )
        ]:
            yield archive

    @set_required_access_v2('events:DescribeReplay', ignore=True)
    def collect_replay_description(self, name):
        return self.client.describe_replay(ReplayName=name)

    def collect_replay(self, replay):
        name = replay.get('ReplayName')
        replay.update({
            self.agent.create_arn(
                'AWS::Events::Replay',
                self.location_info,
                name
            )
        })
        description = self.collect_replay_description(name) or replay
        return ReplayData(summary=replay, description=description)

    def collect_replays(self):
        for replay in [
                self.collect_replay(replay) for replay in client_array_operation(
                    self.client,
                    'list_replays',
                    'Replays'
                )
        ]:
            yield replay

    def collect_event_source(self, summary):
        # TODO check if we get all attributes otherwise describe is necessary
        return summary

    def collect_event_sources(self):
        for source in [
                self.collect_event_source(source) for source in client_array_operation(
                    self.client,
                    'list_event_sources',
                    'EventSources'
                )
        ]:
            yield source

    def process_all(self, filter=None):
        # print('{}.process_all starter with filter {}'.format(self.__class__.__name__, filter))
        if not filter or "api_destinations" in filter:
            self.process_api_destinations()
        if not filter or "connections" in filter:
            self.process_connections()
        if not filter or "sources" in filter:
            self.process_event_sources()
        if not filter or "event_buses" in filter:
            self.process_event_buses()
        if not filter or "archives" in filter:
            self.process_archives()
        if not filter or "replays" in filter:
            self.process_replays()

    @set_required_access_v2('events:ListEventBuses', ignore=True)
    def process_event_buses(self):
        # print('Processing of EventBuses started')
        for event_bus in self.collect_event_buses():
            self.process_event_bus(event_bus)

    @set_required_access_v2('events:ListApiDestinations', ignore=True)
    def process_api_destinations(self):
        for destination in self.collect_api_destinations():
            self.process_api_destination(destination)

    @set_required_access_v2('events:ListConnections', ignore=True)
    def process_connections(self):
        for connection in self.collect_connections():
            self.process_connection(connection)

    @set_required_access_v2('events:ListArchives', ignore=True)
    def process_archives(self):
        for archive in self.collect_archives():
            self.process_archive(archive)

    @set_required_access_v2('events:ListReplays', ignore=True)
    def process_replays(self):
        for replay in self.collect_replays():
            self.process_replay(replay)

    @set_required_access_v2('events:ListEventSources', ignore=True)
    def process_event_sources(self):
        for event_source in self.collect_event_sources():
            self.process_event_source(event_source)

    def process_target(self, rule_arn, target):
        output = make_valid_data(target)
        target = RuleTarget(target, strict=False)
        target.validate()
        output["Name"] = target.Id
        self.emit_component(target.Id, "aws.events.target", output)
        self.agent.relation(rule_arn, target.Id, "has resource", {})
        # strip region for sqs
        arn = target.Arn
        if arn.startswith('arn:aws:sqs:'):
            parts = arn.split(':')
            arn = self.agent.create_arn('AWS::SQS::Queue', self.location_info, parts[5])
        self.agent.relation(target.Id, arn, "uses service", {})
        if target.RoleArn:
            self.agent.relation(target.Id, target.RoleArn, "uses service", {})

    def process_rule(self, bus_arn, rule):
        output = make_valid_data(rule.description)
        output["Tags"] = rule.tags
        rule_description = RuleDescription(rule.description, strict=False)
        rule_description.validate()
        self.emit_component(rule_description.Arn, 'aws.events.rule', output)
        self.agent.relation(rule_description.Arn, bus_arn, 'uses service', {})
        if rule_description.RoleArn:
            self.agent.relation(rule_description.Arn, rule_description.RoleArn, "uses service", {})
        for target in rule.targets:
            self.process_target(rule_description.Arn, target)

    def process_event_bus(self, data):
        event_bus_description = EventBusDescription(data.description, strict=False)
        event_bus_description.validate()
        output = make_valid_data(data.description)
        output["Tags"] = data.tags
        self.emit_component(event_bus_description.Arn, self.COMPONENT_TYPE, output)
        for rule in data.rules:
            self.process_rule(event_bus_description.Arn, rule)

    def process_connection(self, data):
        output = make_valid_data(data.description)
        connection = ApiConnection(data.description, strict=False)
        connection.validate()
        self.emit_component(connection.ConnectionArn, 'aws.events.connection', output)
        if connection.SecretArn:
            self.agent.relation(connection.ConnectionArn, connection.SecretArn, 'uses service', {})

    def process_api_destination(self, data):
        destination = ApiDestination(data.description, strict=False)
        destination.validate()
        output = make_valid_data(data.description)
        self.emit_component(destination.ApiDestinationArn, 'aws.events.api_destination', output)
        self.agent.relation(destination.ApiDestinationArn, destination.ConnectionArn, 'uses service', {})

    def process_archive(self, data):
        archive = Archive(data.description, strict=False)
        archive.validate()
        output = make_valid_data(data.description)
        output["Name"] = archive.ArchiveName
        self.emit_component(archive.ArchiveArn, 'aws.events.archive', output)
        if archive.EventSourceArn:
            self.agent.relation(archive.ArchiveArn, archive.EventSourceArn, 'uses service', {})

    def process_replay(self, data):
        replay = Replay(data.description, strict=False)
        replay.validate()
        output = make_valid_data(data.description)
        output["Name"] = replay.ReplayName
        self.emit_component(replay.ReplayArn, 'aws.events.replay', output)
        if replay.EventSourceArn:
            self.agent.relation(replay.ReplayArn, replay.EventSourceArn, 'uses service', {})
        if replay.Destination and replay.Destination.Arn:
            self.agent.relation(replay.ReplayArn, replay.Destination.Arn, 'uses service', {})

    def process_event_source(self, data):
        source = EventSource(data, strict=False)
        source.validate()
        output = make_valid_data(data)
        if source.State != 'DELETED':
            self.emit_component(source.Arn, 'aws.events.event_source', output)
            if source.State == 'ACTIVE':
                bus_arn = self.agent.create_arn(self.CLOUDFORMATION_TYPE, self.location_info, source.Name)
                self.agent.relation(source.Arn, bus_arn, 'uses service', {})
