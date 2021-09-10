# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .cloudtrail import CloudtrailCollector
from .flowlogs import FlowLogCollector
import logging
import boto3
import time
import traceback
from botocore.exceptions import ClientError
from schematics import Model
from schematics.types import StringType, ListType, DictType, IntType
from botocore.config import Config
from stackstate_checks.base import AgentCheck, TopologyInstance
from .resources import ResourceRegistry, type_arn, RegisteredResourceCollector
from .utils import location_info, correct_tags, capitalize_keys, seconds_ago
from datetime import datetime, timedelta
import pytz
import concurrent.futures
import threading


DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT,
    )
)

DEFAULT_COLLECTION_INTERVAL = 60


class InitConfig(Model):
    aws_access_key_id = StringType(required=True)
    aws_secret_access_key = StringType(required=True)
    external_id = StringType(required=True)
    full_run_interval = IntType(default=3600)


class InstanceInfo(Model):
    role_arn = StringType(required=True)
    regions = ListType(StringType)
    tags = ListType(StringType, default=[])
    arns = DictType(StringType, default={})
    apis_to_run = ListType(StringType)
    log_bucket_name = StringType()


class AwsTopologyCheck(AgentCheck):
    """Collects AWS Topology and sends them to STS."""

    INSTANCE_TYPE = "aws-v2"  # TODO should we add _topology?
    SERVICE_CHECK_CONNECT_NAME = "aws_topology.can_connect"
    SERVICE_CHECK_EXECUTE_NAME = "aws_topology.can_execute"
    SERVICE_CHECK_UPDATE_NAME = "aws_topology.can_update"

    INSTANCE_SCHEMA = InstanceInfo

    @staticmethod
    def get_account_id(instance_info):
        return instance_info.role_arn.split(":")[4]

    def get_instance_key(self, instance_info):
        return TopologyInstance(self.INSTANCE_TYPE, str(self.get_account_id(instance_info)))

    def must_run_full(self, interval):
        self.log.info('Checking if full run is necessary')
        if not hasattr(self, 'last_full_topology'):
            # Create empty state
            self.log.info('  Result => YES (first run)')
            return True
        secs = seconds_ago(self.last_full_topology)
        self.log.info('  Result => {} (Last run was {} seconds ago, interval is set to {})'.format(
            "YES" if secs > interval else "NO",
            int(secs),
            interval)
        )
        return secs > interval

    def check(self, instance_info):
        try:
            init_config = InitConfig(self.init_config)
            init_config.validate()
            aws_client = AwsClient(init_config)
            self.service_check(self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.OK, tags=instance_info.tags)
        except Exception as e:
            msg = "AWS connection failed: {}".format(e)
            self.log.error(msg)
            self.service_check(
                self.SERVICE_CHECK_CONNECT_NAME, AgentCheck.CRITICAL, message=msg, tags=instance_info.tags
            )
            return

        self.delete_ids = []
        self.components_seen = set()
        if self.must_run_full(init_config.full_run_interval):
            try:
                self.log.info('Starting FULL topology scan')
                self.last_full_topology = datetime.utcnow().replace(tzinfo=pytz.utc)
                self.get_topology(instance_info, aws_client)
                self.log.info('Finished FULL topology scan (no exceptions)')
                self.service_check(self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.OK, tags=instance_info.tags)
            except Exception as e:
                msg = "AWS topology collection failed: {}".format(e)
                self.log.error(msg)
                self.service_check(
                    self.SERVICE_CHECK_EXECUTE_NAME, AgentCheck.WARNING, message=msg, tags=instance_info.tags
                )

        try:
            self.get_topology_update(instance_info, aws_client)
            self.get_flowlog_update(instance_info, aws_client)
            self.service_check(self.SERVICE_CHECK_UPDATE_NAME, AgentCheck.OK, tags=instance_info.tags)
        except Exception as e:
            msg = "AWS topology update failed: {}".format(e)
            self.log.error(msg)
            self.service_check(
                self.SERVICE_CHECK_UPDATE_NAME, AgentCheck.WARNING, message=msg, tags=instance_info.tags
            )

    def get_topology(self, instance_info, aws_client):
        """Gets AWS Topology returns them in Agent format."""

        self.start_snapshot()

        errors = []
        agent_proxy = AgentProxy(self, instance_info.role_arn, self.log)
        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for region in instance_info.regions:
                session = aws_client.get_session(instance_info.role_arn, region)
                registry = ResourceRegistry.get_registry()["regional" if region != "global" else "global"]
                keys = (
                    [key for key in registry.keys()]
                    if instance_info.apis_to_run is None
                    else [api.split("|")[0] for api in instance_info.apis_to_run]
                )
                for api in keys:
                    if not registry.get(api):
                        continue
                    client = None
                    location = location_info(self.get_account_id(instance_info), session.region_name)
                    filter = None
                    if instance_info.apis_to_run is not None:
                        for to_run in instance_info.apis_to_run:
                            if (api + "|") in to_run:
                                filter = to_run.split("|")[1]
                    if client is None:
                        client = session.client(api) if api != "noclient" else None
                    processor = registry[api](location.clone(), client, agent_proxy)
                    self.log.debug("Starting account {} API {} for region {}".format(
                        self.get_account_id(instance_info),
                        api,
                        session.region_name
                    ))
                    futures[executor.submit(processor.process_all, filter)] = {
                        "location": location.clone(),
                        "api": api,
                        "processor": processor,
                    }
                    # processor.process_all(filter=filter)
                    # self.delete_ids += processor.get_delete_ids()
            for future in concurrent.futures.as_completed(futures):
                spec = futures[future]
                try:
                    future.result()
                    self.log.debug("Finished account {} API {} for region {}".format(
                        self.get_account_id(instance_info),
                        spec["api"],
                        spec["location"].Location.AwsRegion
                    ))
                except Exception as e:
                    event = {
                        "timestamp": int(time.time()),
                        "event_type": "aws_agent_check_error",
                        "msg_title": e.__class__.__name__ + " in api " + spec["api"],
                        "msg_text": str(e),
                        "tags": [
                            "aws_region:" + spec["location"].Location.AwsRegion,
                            "account_id:" + spec["location"].Location.AwsAccount,
                            "process:" + spec["api"],
                        ],
                    }
                    self.event(event)
                    errors.append("API %s ended with exception: %s %s" % (spec["api"], str(e), traceback.format_exc()))
        # TODO this should be for tests, in production these relations should not be sent out
        self.log.info('Finalize FULL scan (#components = {})'.format(len(agent_proxy.components_seen)))
        agent_proxy.finalize_account_topology()
        self.components_seen = agent_proxy.components_seen
        self.delete_ids += agent_proxy.delete_ids

        if len(errors) > 0:
            self.log.warning("Not sending 'stop_snapshot' because one or more APIs returned with exceptions")
            raise Exception("get_topology gave following exceptions: %s" % ", ".join(errors))

        self.stop_snapshot()

    def get_topology_update(self, instance_info, aws_client):
        not_before = self.last_full_topology
        agent_proxy = AgentProxy(self, instance_info.role_arn, self.log)
        listen_for = ResourceRegistry.CLOUDTRAIL
        for region in instance_info.regions:
            session = aws_client.get_session(instance_info.role_arn, region)
            events_per_api = {}
            collector = CloudtrailCollector(
                bucket_name=instance_info.log_bucket_name,
                account_id=self.get_account_id(instance_info),
                session=session,
                agent=agent_proxy,
                log=self.log
            )
            # collect the events (ordering is most recent event first)
            for event in collector.get_messages(not_before):
                msgs = listen_for.get(event["eventSource"])
                if not msgs and event.get("apiVersion"):
                    msgs = listen_for.get(event["apiVersion"] + "-" + event["eventSource"])
                if isinstance(msgs, dict):
                    event_name = event.get("eventName")
                    event_class = msgs.get(event_name)
                    if event_class:
                        if isinstance(event_class, bool):
                            agent_proxy.warning("should interpret: " + event["eventName"] + "-" + event["eventSource"])
                        elif issubclass(event_class, RegisteredResourceCollector):
                            # the new way of event handling
                            events = events_per_api.get(event_class.API)
                            if events:
                                events.append(event)
                            else:
                                events_per_api[event_class.API] = [event]

            # TODO if full snapshot ran just before we can use components_seen here too
            # operation type C=create D=delete U=update E=event
            # component seen: YES
            #  C -> skip
            #  U -> timing, do is safe
            #  D -> timing!, skip will leave component in for hour
            #  E -> do
            # component seen: NO
            #  C -> try
            #  U -> try
            #  D -> skip
            #  E -> timing, skip (!could have create before)
            location = location_info(self.get_account_id(instance_info), session.region_name)
            registry = ResourceRegistry.get_registry()["regional" if region != "global" else "global"]
            for api in events_per_api:
                client = session.client(api) if api != "noclient" else None
                resources_seen = set()
                processor = registry[api](location.clone(), client, agent_proxy)
                for event in events_per_api[api]:
                    processor.process_cloudtrail_event(event, resources_seen)

        self.delete_ids += agent_proxy.delete_ids

    def get_flowlog_update(self, instance_info, aws_client):
        not_before = self.last_full_topology - timedelta(seconds=60*60)
        agent_proxy = AgentProxy(self, instance_info.role_arn, self.log)
        for region in instance_info.regions:
            session = aws_client.get_session(instance_info.role_arn, region)
            location = location_info(self.get_account_id(instance_info), session.region_name)
            collector = FlowLogCollector(
                bucket_name=instance_info.log_bucket_name,
                account_id=self.get_account_id(instance_info),
                session=session,
                location_info=location,
                agent=agent_proxy,
                log=self.log
            )
            collector.read_flow_log(not_before)


class AgentProxy(object):
    def __init__(self, agent, role_name, log):
        self.agent = agent
        self.delete_ids = []
        self.components_seen = set()
        self.parked_relations = []
        self.role_name = role_name
        self.warnings = {}
        self.lock = threading.Lock()
        self.log = log

    def component(self, location, id, type, data, streams=None, checks=None):
        self.components_seen.add(id)
        data.update(location.to_primitive())
        self.agent.component(id, type, correct_tags(capitalize_keys(data)), streams, checks)
        relations_to_send = []
        with self.lock:
            for i in range(len(self.parked_relations) - 1, -1, -1):
                relation = self.parked_relations[i]
                if relation["source_id"] == id and relation["target_id"] in self.components_seen:
                    relations_to_send.append(relation)
                    self.parked_relations.remove(relation)
                if relation["target_id"] == id and relation["source_id"] in self.components_seen:
                    self.parked_relations.remove(relation)
                    relations_to_send.append(relation)
        for relation in relations_to_send:
            self.agent.relation(
                relation["source_id"], relation["target_id"], relation["type"],
                relation["data"], relation['streams'], relation['checks']
            )

    def relation(self, source_id, target_id, type, data, streams=None, checks=None):
        if source_id in self.components_seen and target_id in self.components_seen:
            self.agent.relation(source_id, target_id, type, data, streams, checks)
        else:
            self.parked_relations.append(
                {"type": type, "source_id": source_id, "target_id": target_id,
                 "data": data, 'streams': streams, 'checks': checks}
            )

    def finalize_account_topology(self):
        for relation in self.parked_relations:
            self.agent.relation(relation["source_id"], relation["target_id"], relation["type"], relation["data"])
        for warning in self.warnings:
            self.agent.warning(warning + " was encountered {} time(s).".format(self.warnings[warning]))

    def event(self, event):
        self.agent.event(event)

    def gauge(self, name, value, tags=None, hostname=None, device_name=None):
        self.agent.log.info('gauge %s: %s %s', name, value, tags)
        self.agent.gauge(name, value, tags, hostname, device_name)

    def delete(self, id):
        self.delete_ids.append(id)

    def warning(self, error, **kwargs):
        # TODO make a list of max 5 of the resources impacted
        warning = self.warnings.get(error, 0) + 1
        self.warnings[error] = warning

    @staticmethod
    def create_arn(type, location, resource_id=""):
        func = type_arn.get(type)
        if func:
            return func(
                region=location.Location.AwsRegion, account_id=location.Location.AwsAccount, resource_id=resource_id
            )
        return "UNSUPPORTED_ARN-" + type + "-" + resource_id

    def create_security_group_relations(self, resource_id, resource_data, security_group_field="SecurityGroups"):
        if resource_data.get(security_group_field):
            for security_group_id in resource_data[security_group_field]:
                self.relation(resource_id, security_group_id, "uses-service", {})


class AwsClient:
    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)
        self.external_id = config.external_id
        self.aws_access_key_id = config.aws_access_key_id
        self.aws_secret_access_key = config.aws_secret_access_key

        if self.aws_secret_access_key and self.aws_access_key_id:
            self.sts_client = boto3.client(
                "sts",
                config=DEFAULT_BOTO3_CONFIG,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        else:
            # Rely on credential provider chain to find credentials
            try:
                self.sts_client = boto3.client("sts", config=DEFAULT_BOTO3_CONFIG)
            except Exception as e:
                raise Exception("No credentials found, the following exception was given: %s" % e)

    def get_session(self, role_arn, region):
        try:
            # This should fail as it means it was able to successfully use the role without an external ID
            role = self.sts_client.assume_role(RoleArn=role_arn, RoleSessionName="sts-agent-id-test")
            # This override should not be (publicly) documented
            if self.external_id != "disable_external_id_this_is_unsafe":
                raise Exception(
                    "No external ID has been set for this role." + "For security reasons, please set the external ID."
                )
        except ClientError as error:
            if error.response["Error"]["Code"] == "AccessDenied":
                try:
                    role = self.sts_client.assume_role(
                        RoleArn=role_arn, RoleSessionName="sts-agent-check-%s" % region, ExternalId=self.external_id
                    )
                except Exception as error:
                    raise Exception("Unable to assume role %s. Error: %s" % (role_arn, error))
            else:
                raise error

        return boto3.Session(
            region_name=region if region != "global" else "us-east-1",
            aws_access_key_id=role["Credentials"]["AccessKeyId"],
            aws_secret_access_key=role["Credentials"]["SecretAccessKey"],
            aws_session_token=role["Credentials"]["SessionToken"],
        )
