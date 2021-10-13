# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
import copy
import inspect
import json
import logging
import re
import traceback
import unicodedata
from collections import defaultdict
from os.path import basename
from functools import reduce


import yaml
from six import PY3, iteritems, iterkeys, text_type, string_types, integer_types

try:
    import datadog_agent
    from ..log import init_logging

    init_logging()
except ImportError:
    from ..stubs import datadog_agent
    from ..stubs.log import init_logging

    init_logging()

try:
    import aggregator

    using_stub_aggregator = False
except ImportError:
    from ..stubs import aggregator

    using_stub_aggregator = True

try:
    import topology

    using_stub_topology = False
except ImportError:
    from ..stubs import topology

    using_stub_topology = True

try:
    import telemetry

    using_stub_telemetry = False
except ImportError:
    from ..stubs import telemetry

    using_stub_telemetry = True

from ..config import is_affirmative
from ..constants import ServiceCheck
from ..utils.common import ensure_string, ensure_unicode, to_string
from ..utils.proxy import config_proxy_skip
from ..utils.limiter import Limiter
from ..utils.identifiers import Identifiers
from ..utils.telemetry import EventStream, MetricStream, ServiceCheckStream, \
    ServiceCheckHealthChecks, Event
from ..utils.health_api import Health, HealthStream, HealthStreamUrn, HealthCheckData, HealthApi
from ..utils.persistent_state import StateDescriptor, StateManager
from deprecated.sphinx import deprecated

if datadog_agent.get_config('disable_unsafe_yaml'):
    from ..ddyaml import monkey_patch_pyyaml

    monkey_patch_pyyaml()

# Metric types for which it's only useful to submit once per set of tags
ONE_PER_CONTEXT_METRIC_TYPES = [
    aggregator.GAUGE,
    aggregator.RATE,
    aggregator.MONOTONIC_COUNT,
]


class _TopologyInstanceBase(object):
    """
    Data structure for defining a topology instance, a unique identifier for a topology source.

    This is not meant to be used in checks.
    """

    def __init__(self, type, url, with_snapshots=False):
        self.type = type
        self.url = url
        self.with_snapshots = with_snapshots

    def to_dict(self):
        return {"type": self.type, "url": self.url}

    def tags(self):
        return ["integration-type:{}".format(self.type), "integration-url:{}".format(self.url)]

    def __eq__(self, other):
        if not isinstance(other, TopologyInstance):
            return False

        return self.type == other.type and self.url == other.url

    def __hash__(self):
        return hash((self.type, self.url))


class NoIntegrationInstance(_TopologyInstanceBase):
    """
    Does not provide a topology `instance` and it is the default if the check does not provide a topology instance key
    Obviously this also disables monitoring for the integration check.

    It is not meant to be used in checks.
    """

    def __init__(self):
        _TopologyInstanceBase.__init__(self, type="agent", url="integrations", with_snapshots=False)

    def tags(self):
        return []


class AgentIntegrationInstance(_TopologyInstanceBase):
    """
    The topology `instance` that this class represents directly correlates to the Agent StackPack
    and therefore the Agent integration synchronization.

    This enables also monitoring for the integration check.
    """

    def __init__(self, integration, name):
        self.integration = integration
        self.name = name
        _TopologyInstanceBase.__init__(self, type="agent", url="integrations", with_snapshots=False)

    def tags(self):
        return ["integration-type:{}".format(self.integration), "integration-url:{}".format(self.name)]

    def __eq__(self, other):
        if (isinstance(other, AgentIntegrationInstance)):
            return self.integration == other.integration and self.name == other.name
        return False


class TopologyInstance(_TopologyInstanceBase):
    """
    The topology `instance` that this class represents directly correlates to a specific StackPack instance
    and therefore a that StackPack synchronization.

    This enables also monitoring for the integration check.
    """
    pass


StackPackInstance = TopologyInstance


class AgentCheckBase(object):
    """
    The base class for any Agent based integrations
    """
    OK, WARNING, CRITICAL, UNKNOWN = ServiceCheck

    """
    DEFAULT_METRIC_LIMIT allows to set a limit on the number of metric name and tags combination
    this check can send per run. This is useful for checks that have an unbounded
    number of tag values that depend on the input payload.
    The logic counts one set of tags per gauge/rate/monotonic_count call, and deduplicates
    sets of tags for other metric types. The first N sets of tags in submission order will
    be sent to the aggregator, the rest are dropped. The state is reset after each run.

    See https://github.com/DataDog/integrations-core/pull/2093 for more information
    """
    DEFAULT_METRIC_LIMIT = 0

    """
    INSTANCE_SCHEMA allows checks to specify a schematics Schema that is used for the instance in self.check
    """
    INSTANCE_SCHEMA = None

    """
    STATE_FIELD_NAME is used to determine to which key the check state should be set, defaults to `state`
    """
    STATE_FIELD_NAME = 'state'

    def __init__(self, *args, **kwargs):
        self.check_id = ''
        self.metrics = defaultdict(list)
        self.name = kwargs.get('name', '')
        self.init_config = kwargs.get('init_config', {})
        self.agentConfig = kwargs.get('agentConfig', {})
        self.warnings = []
        self.metric_limiter = None
        self.instances = kwargs.get('instances', [])

        if len(args) > 0:
            self.name = args[0]
        if len(args) > 1:
            self.init_config = args[1]
        if len(args) > 2:
            if len(args) > 3 or 'instances' in kwargs:
                # old-style init: the 3rd argument is `agentConfig`
                self.agentConfig = args[2]
                if len(args) > 3:
                    self.instances = args[3]
            else:
                # new-style init: the 3rd argument is `instances`
                self.instances = args[2]

        # Agent 6+ will only have one instance
        self.instance = self.instances[0] if self.instances else {}

        # `self.hostname` is deprecated, use `datadog_agent.get_hostname()` instead
        self.hostname = datadog_agent.get_hostname()

        # returns the cluster name if the check is running in Kubernetes / OpenShift
        self.cluster_name = AgentCheckBase.get_cluster_name()

        self.log = logging.getLogger('{}.{}'.format(__name__, self.name))
        if using_stub_aggregator:
            self.log.warn("Using stub aggregator api")
        if using_stub_topology:
            self.log.warn("Using stub topology api")
        if using_stub_telemetry:
            self.log.warn("Using stub telemetry api")
        self.state_manager = StateManager(self.log)
        self._deprecations = {}
        # Set proxy settings
        self.proxies = self._get_requests_proxy()
        if not self.init_config:
            self._use_agent_proxy = True
        else:
            self._use_agent_proxy = is_affirmative(self.init_config.get('use_agent_proxy', True))

        self.default_integration_http_timeout = float(self.agentConfig.get('default_integration_http_timeout', 9))

        # Will be initialized as part of the check, to allow for proper error reporting there if initialization fails
        self.health = None

    def _init_health_api(self):
        if self.health is not None:
            return

        stream_spec = self.get_health_stream(self._get_instance_schema(self.instance))
        if stream_spec:
            # 15 seconds is the default interval (see defaults.DefaultCheckInterval in the core agent)
            min_collection_interval = self.instance.get('min_collection_interval', 15)
            repeat_interval_seconds = stream_spec.repeat_interval_seconds or min_collection_interval
            expiry_seconds = stream_spec.expiry_seconds
            # Only apply a default expiration when we are using substreams
            if expiry_seconds is None and stream_spec.sub_stream != "":
                expiry_seconds = repeat_interval_seconds * 4
            self.health = HealthApi(self, stream_spec, expiry_seconds, repeat_interval_seconds)

    def _check_run_base(self, default_result):
        try:
            # start auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_start_snapshot(self, self.check_id, self._get_instance_key_dict())

            # create integration instance components for monitoring purposes
            self.create_integration_instance()

            # Initialize the health api
            self._init_health_api()

            # create a copy of the check instance, get state if any and add it to the instance object for the check
            instance = self.instances[0]
            check_instance = copy.deepcopy(instance)
            # if this instance has some state then set it to state
            current_state = copy.deepcopy(self.state_manager.get_state(self._get_state_descriptor()))
            if current_state:
                check_instance[self.STATE_FIELD_NAME] = current_state

            check_instance = self._get_instance_schema(check_instance)
            self.check(check_instance)

            # set the state from the check instance
            # call self._get_state_descriptor method to get the instance key if it is update in the check run
            # example: aws-xray
            self.state_manager.set_state(self._get_state_descriptor(), check_instance.get(self.STATE_FIELD_NAME))

            # stop auto snapshot if with_snapshots is set to True
            if self._get_instance_key().with_snapshots:
                topology.submit_stop_snapshot(self, self.check_id, self._get_instance_key_dict())

            result = default_result
        except Exception as e:
            result = json.dumps([
                {
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            ])
        finally:
            if self.metric_limiter:
                self.metric_limiter.reset()

        return result

    def commit_state(self, state, flush=True):
        """
        commit_state can be used to immediately set (and optionally flush) state in the agent, instead of first
        completing
        the check
        """
        self.state_manager.set_state(self._get_state_descriptor(), state, flush)

    def set_metric_limits(self):
        try:
            metric_limit = self.instances[0].get('max_returned_metrics', self.DEFAULT_METRIC_LIMIT)
            # Do not allow to disable limiting if the class has set a non-zero default value
            if metric_limit == 0 and self.DEFAULT_METRIC_LIMIT > 0:
                metric_limit = self.DEFAULT_METRIC_LIMIT
                self.warning(
                    'Setting max_returned_metrics to zero is not allowed, reverting '
                    'to the default of {} metrics'.format(self.DEFAULT_METRIC_LIMIT)
                )
        except Exception:
            metric_limit = self.DEFAULT_METRIC_LIMIT
        if metric_limit > 0:
            self.metric_limiter = Limiter(self.name, 'metrics', metric_limit, self.warning)

    def _get_state_descriptor(self):
        integration_instance = self._get_instance_key()
        instance_key = to_string(
            self.normalize("instance.{}.{}".format(integration_instance.type, integration_instance.url),
                           extra_disallowed_chars=b":")
        )

        return StateDescriptor(instance_key, self.get_check_state_path())

    @staticmethod
    def get_cluster_name():
        """
        returns the cluster name if the check is running in Kubernetes / OpenShift
        """
        return datadog_agent.get_clustername()

    @staticmethod
    def get_hostname():
        """
        returns the hostname
        """
        return datadog_agent.get_hostname()

    @staticmethod
    def load_config(yaml_str):
        """
        Convenience wrapper to ease programmatic use of this class from the C API.
        """
        return yaml.safe_load(yaml_str)

    @property
    def in_developer_mode(self):
        self._log_deprecation('in_developer_mode')
        return False

    def _context_uid(self, mtype, name, tags=None, hostname=None):
        return '{}-{}-{}-{}'.format(mtype, name, tags if tags is None else hash(frozenset(tags)), hostname)

    @staticmethod
    def _check_not_none(argument_name, value):
        if value is None:
            raise ValueError("Got None value for argument {}".format(argument_name))

    @staticmethod
    def _check_is_string(argumentName, value):
        AgentCheckBase._check_not_none(argumentName, value)
        if not isinstance(value, string_types):
            AgentCheckBase._raise_unexpected_type(argumentName, value, "string")

    @staticmethod
    def _raise_unexpected_type(argumentName, value, expected):
        raise ValueError("Got unexpected {} for argument {}, expected {}".format(type(value), argumentName, expected))

    @staticmethod
    def _check_struct_value(argumentName, value):
        if value is None or isinstance(value, string_types) or isinstance(value, integer_types) or \
                isinstance(value, float) or isinstance(value, bool):
            return
        elif isinstance(value, dict):
            for k in value:
                AgentCheckBase._check_struct_value("{}.{}".format(argumentName, k), value[k])
        elif isinstance(value, list):
            for idx, val in enumerate(value):
                AgentCheckBase._check_struct_value("{}[{}]".format(argumentName, idx), val)
        else:
            AgentCheckBase._raise_unexpected_type(argumentName, value, "string, int, dictionary, list or None value")

    @staticmethod
    def _check_struct(argumentName, value):
        if isinstance(value, dict):
            AgentCheckBase._check_struct_value(argumentName, value)
        else:
            AgentCheckBase._raise_unexpected_type(argumentName, value, "dictionary or None value")

    def get_health_stream(self, instance):
        """
        Integration checks can override this if they want to be producing a health stream. Defining the will
        enable self.health() calls

        :return: a class extending HealthStream
        """
        return None

    def _get_instance_schema(self, instance):
        check_instance = instance

        # if this check has a instance schema defined, cast it into that type and validate it
        if self.INSTANCE_SCHEMA:
            check_instance = self.INSTANCE_SCHEMA(instance, strict=False)  # strict=False ignores extra fields
            check_instance.validate()
        return check_instance

    def get_instance_key(self, instance):
        """
        Integration checks can override this based on their needs.

        :param instance: AgentCheck instance
        :return: a class extending _TopologyInstanceBase
        """
        return NoIntegrationInstance()

    def _get_instance_key(self):
        check_instance = self._get_instance_schema(self.instance)

        value = self.get_instance_key(check_instance)
        if value is None:
            AgentCheckBase._raise_unexpected_type("get_instance_key()", "None", "dictionary")
        if not isinstance(value, (TopologyInstance, AgentIntegrationInstance, NoIntegrationInstance)):
            AgentCheckBase._raise_unexpected_type("get_instance_key()",
                                                  value,
                                                  "TopologyInstance, AgentIntegrationInstance or "
                                                  "DefaultIntegrationInstance")
        if not isinstance(value.type, str):
            raise ValueError("Instance requires a 'type' field of type 'string'")
        if not isinstance(value.url, str):
            raise ValueError("Instance requires a 'url' field of type 'string'")

        return value

    def _get_instance_key_dict(self):
        return self._get_instance_key().to_dict()

    def get_instance_proxy(self, instance, uri, proxies=None):
        proxies = proxies if proxies is not None else self.proxies.copy()

        deprecated_skip = instance.get('no_proxy', None)
        skip = (
            is_affirmative(instance.get('skip_proxy', not self._use_agent_proxy)) or is_affirmative(deprecated_skip)
        )

        if deprecated_skip is not None:
            self._log_deprecation('no_proxy')

        return config_proxy_skip(proxies, uri, skip)

    # TODO(olivier): implement service_metadata if it's worth it
    def service_metadata(self, meta_name, value):
        pass

    def check(self, instance):
        raise NotImplementedError

    def warning(self, warning_message):
        pass

    def normalize(self, metric, prefix=None, fix_case=False, extra_disallowed_chars=None):
        """
        Turn a metric into a well-formed metric name
        prefix.b.c
        :param metric The metric name to normalize
        :param prefix A prefix to to add to the normalized name, default None
        :param fix_case A boolean, indicating whether to make sure that the metric name returned is in "snake_case"
        """
        if isinstance(metric, text_type):
            metric = unicodedata.normalize('NFKD', metric).encode('ascii', 'ignore')

        if fix_case:
            name = self.convert_to_underscore_separated(metric)
            if prefix is not None:
                prefix = self.convert_to_underscore_separated(prefix)
        elif extra_disallowed_chars:
            name = re.sub(br"[,\+\*\-/()\[\]{}\s" + extra_disallowed_chars + br"]", b"_", metric)
        else:
            name = re.sub(br"[,\+\*\-/()\[\]{}\s]", b"_", metric)
        # Eliminate multiple _
        name = re.sub(br"__+", b"_", name)
        # Don't start/end with _
        name = re.sub(br"^_", b"", name)
        name = re.sub(br"_$", b"", name)
        # Drop ._ and _.
        name = re.sub(br"\._", b".", name)
        name = re.sub(br"_\.", b".", name)

        if prefix is not None:
            return ensure_string(prefix) + b"." + name
        else:
            return name

    FIRST_CAP_RE = re.compile(br'(.)([A-Z][a-z]+)')
    ALL_CAP_RE = re.compile(br'([a-z0-9])([A-Z])')
    METRIC_REPLACEMENT = re.compile(br'([^a-zA-Z0-9_.]+)|(^[^a-zA-Z]+)')
    DOT_UNDERSCORE_CLEANUP = re.compile(br'_*\._*')

    def convert_to_underscore_separated(self, name):
        """
        Convert from CamelCase to camel_case
        And substitute illegal metric characters
        """
        metric_name = self.FIRST_CAP_RE.sub(br'\1_\2', ensure_string(name))
        metric_name = self.ALL_CAP_RE.sub(br'\1_\2', metric_name).lower()
        metric_name = self.METRIC_REPLACEMENT.sub(br'_', metric_name)
        return self.DOT_UNDERSCORE_CLEANUP.sub(br'.', metric_name).strip(b'_')

    def component(self, id, type, data, streams=None, checks=None):
        integration_instance = self._get_instance_key()
        try:
            fixed_data = self._sanitize(data)
            fixed_streams = self._sanitize(streams)
            fixed_checks = self._sanitize(checks)
        except (UnicodeError, TypeError):
            return
        data = self._map_component_data(id, type, integration_instance, fixed_data, fixed_streams, fixed_checks)
        topology.submit_component(self, self.check_id, self._get_instance_key_dict(), id, type, data)
        return {"id": id, "type": type, "data": data}

    def _map_component_data(self, id, type, integration_instance, data, streams=None, checks=None,
                            add_instance_tags=True):
        AgentCheckBase._check_is_string("id", id)
        AgentCheckBase._check_is_string("type", type)
        if data is None:
            data = {}
        self._check_struct("data", data)
        data = self._map_streams_and_checks(data, streams, checks)
        data = self._map_identifier_mappings(type, data)
        data = self._map_stackstate_tags_and_instance_config(data)

        if add_instance_tags:
            # add topology instance for view filtering
            data['tags'] = sorted(list(set(data.get('tags', []) + integration_instance.tags())))
        self._check_struct("data", data)
        return data

    def relation(self, source, target, type, data, streams=None, checks=None):
        try:
            fixed_data = self._sanitize(data)
            fixed_streams = self._sanitize(streams)
            fixed_checks = self._sanitize(checks)
        except (UnicodeError, TypeError):
            return
        data = self._map_relation_data(source, target, type, fixed_data, fixed_streams, fixed_checks)
        topology.submit_relation(self, self.check_id, self._get_instance_key_dict(), source, target, type, data)
        return {"source_id": source, "target_id": target, "type": type, "data": data}

    def _map_stackstate_tags_and_instance_config(self, data):
        # Extract or create the tags and identifier objects
        tags = data.get('tags', [])
        identifiers = data.get("identifiers", [])

        # Find the stackstate-identifiers within tags
        identifier_tag = next((tag for tag in tags if ("stackstate-identifiers:" in tag)), None)

        # We attempt to split and map out the identifiers specified in the identifier_tag
        # ** Does not support config **
        if isinstance(identifier_tag, str):
            identifier_tag_content = identifier_tag.split('stackstate-identifiers:')[1]
            if len(identifier_tag_content) > 0:
                # Remove the tag if valid identifiers was found
                tags.remove(identifier_tag)

                # Split the list on comma or spaces based values
                result = self.split_on_commas_and_spaces(identifier_tag_content)
                identifiers = identifiers + result

        # Detect single identifiers and set the identifiers object
        single_identifier_tag = self._map_config_and_tags(data, 'stackstate-identifier', 'identifier', False, True)
        if isinstance(single_identifier_tag, str):
            identifiers = identifiers + [single_identifier_tag]

        # Only apply identifiers if we found any
        if len(identifiers) > 0:
            data["identifiers"] = identifiers

        # Attempt to map stackstate-*** tags and configs
        data = self._map_config_and_tags(data, 'stackstate-layer', 'layer')
        data = self._map_config_and_tags(data, 'stackstate-environment', 'environments', True)
        data = self._map_config_and_tags(data, 'stackstate-domain', 'domain')

        return data

    # Regex function used to split a string on commas and/or spaces
    @staticmethod
    def split_on_commas_and_spaces(content):
        if isinstance(content, str):
            """
                We are testing the following with the regex block below
                - Match all spaces if any at the start followed by a must have comma then followed again by a possible
                    single or multiple spaces
                - Second possibility is a single or multiple space only without a comma
                The resulting regex will work on a complex line like the following example:
                    Input: a, b, c,d,e f g h, i , j ,k   ,l  ,  m
                    Result: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm']
            """
            content_list = re.split('(?:\\s+)?,(?:\\s+)?|\\s+', content)

            # Clean out all empty string ''
            clean_identifier_list = list(filter(lambda item: len(item) > 0, content_list))
            return clean_identifier_list
        else:
            return []

    # Generic mapping function for tags or config
    # Attempt to find if the target exists on a tag or config and map that to the origin value
    # There's a optional default value if required
    # Value override order: tags < config.yaml
    def _map_config_and_tags(self, data, target, origin, return_array=False, return_direct_value=False, default=None):
        # Get the first instance and create a deep copy
        instance = self.instances[0] if self.instances is not None and len(self.instances) else {}
        check_instance = copy.deepcopy(instance)

        # Extract or create the tags
        tags = data.get('tags', [])

        # Attempt to find the tag and map its value to a object inside data
        find_tag = next((tag for tag in tags if (target + ':' in tag)), None)
        if isinstance(find_tag, str) and find_tag.index(":") > 0:
            result = [find_tag.split(target + ':')[1]] if return_array is True else find_tag.split(target + ':')[1]
            # Remove the tag from tags if found
            tags.remove(find_tag)
            if return_direct_value is True:
                return result
            data[origin] = result

        elif target in check_instance and isinstance(check_instance[target], str):
            result = [check_instance[target]] if return_array is True else check_instance[target]
            if return_direct_value is True:
                return result
            data[origin] = result

        elif default is not None and isinstance(default, str):
            result = [default] if return_array is True else default
            if return_direct_value is True:
                return result
            data[origin] = result

        if return_direct_value is True and return_array is True:
            return []
        return data

    def _map_relation_data(self, source, target, type, data, streams=None, checks=None):
        AgentCheckBase._check_is_string("source", source)
        AgentCheckBase._check_is_string("target", target)
        AgentCheckBase._check_is_string("type", type)
        self._check_struct("data", data)
        if data is None:
            data = {}
        data = self._map_streams_and_checks(data, streams, checks)
        self._check_struct("data", data)
        return data

    def get_mapping_field_key(self, dictionary, keys, default=None):
        return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."),
                      dictionary)

    def _map_identifier_mappings(self, type, data):
        if "identifier_mappings" not in self.instance:
            self.log.debug("No identifier_mappings section found in configuration. Skipping..")
            return data
        if type in self.instance["identifier_mappings"]:
            type_mapping = self.instance["identifier_mappings"].get(type)
            field_value = self.get_mapping_field_key(data, type_mapping.get("field"))
            if not field_value:
                self.log.warning("The %s field is not found in data section." % (type_mapping.get("field")))
                return data
            identifiers = data.get("identifiers", [])
            identifiers.append('%s%s' % (type_mapping.get("prefix"), field_value))
            data["identifiers"] = identifiers
            return data

    def _map_streams_and_checks(self, data, streams, checks):
        if streams:
            stream_id = -1
            for stream in streams:
                stream.stream_id = stream_id
                if isinstance(stream, MetricStream):
                    if "metrics" in data:
                        data["metrics"].append(stream.to_payload())
                    else:
                        data["metrics"] = [stream.to_payload()]
                elif isinstance(stream, EventStream):
                    if "events" in data:
                        data["events"].append(stream.to_payload())
                    else:
                        data["events"] = [stream.to_payload()]
                elif isinstance(stream, ServiceCheckStream):
                    if "service_checks" in data:
                        data["service_checks"].append(stream.to_payload())
                    else:
                        data["service_checks"] = [stream.to_payload()]
                # decrement for negative id
                stream_id = stream_id - 1
        if checks:
            data["checks"] = []
            for check in checks:
                # single stream check
                if "stream_id" in check:
                    stream_id = next((stream.stream_id for stream in streams if stream.identifier ==
                                      check["stream_id"]), None)
                    if stream_id:
                        data["checks"].append(dict(check, **{"stream_id": stream_id}))
                # denominator and numerator stream check
                if "denominator_stream_id" and "numerator_stream_id" in check:
                    denominator_stream_id = next((stream.stream_id for stream in streams if stream.identifier ==
                                                  check["denominator_stream_id"]), None)
                    numerator_stream_id = next((stream.stream_id for stream in streams if stream.identifier ==
                                                check["numerator_stream_id"]), None)
                    if denominator_stream_id and numerator_stream_id:
                        data["checks"].append(dict(check, **{"denominator_stream_id": denominator_stream_id,
                                                             "numerator_stream_id": numerator_stream_id}))

        return data

    @deprecated(version='2.9.0', reason="Topology Snapshots is enabled by default for all TopologyInstance checks, "
                                        "to disable snapshots use TopologyInstance(type, url, with_snapshots=False) "
                                        "when overriding get_instance_key")
    def start_snapshot(self):
        topology.submit_start_snapshot(self, self.check_id, self._get_instance_key_dict())

    @deprecated(version='2.9.0', reason="Topology Snapshots is enabled by default for all TopologyInstance checks, "
                                        "to disable snapshots use TopologyInstance(type, url, with_snapshots=False) "
                                        "when overriding get_instance_key")
    def stop_snapshot(self):
        topology.submit_stop_snapshot(self, self.check_id, self._get_instance_key_dict())

    def create_integration_instance(self):
        """

        Agent -> Agent Integration -> Agent Integration Instance
        """
        integration_instance = self._get_instance_key()
        instance_type = integration_instance.type
        instance_url = integration_instance.url
        check_id = self.check_id
        if isinstance(integration_instance, AgentIntegrationInstance):
            instance_type = integration_instance.integration
            instance_url = integration_instance.name
        elif isinstance(integration_instance, NoIntegrationInstance):
            # for DefaultIntegrationInstance we don't create integration instances
            return
        else:
            # set the check id for TopologyInstance types, in a AgentIntegrationInstance the data can go to the same
            # check instance ending up on the agent integrations synchronization in StackState with no snapshots
            check_id = "{}:{}".format(instance_type, instance_url)

        # use this as the topology instance so that data ends up in the Agent Integration sync
        default_integration_instance = AgentIntegrationInstance("default", "integration")

        # Agent Component
        agent_external_id = Identifiers.create_agent_identifier(datadog_agent.get_hostname())
        agent_data = {
            "name": "StackState Agent:{}".format(datadog_agent.get_hostname()),
            "hostname": datadog_agent.get_hostname(),
            "tags": ["hostname:{}".format(datadog_agent.get_hostname()), "stackstate-agent"],
            "identifiers": [Identifiers.create_process_identifier(
                datadog_agent.get_hostname(), datadog_agent.get_pid(), datadog_agent.get_create_time()
            )]
        }
        if datadog_agent.get_clustername():
            agent_data["cluster"] = datadog_agent.get_clustername()
        topology.submit_component(self, check_id, default_integration_instance.to_dict(), agent_external_id,
                                  "stackstate-agent",
                                  self._map_component_data(agent_external_id, "stackstate-agent", integration_instance,
                                                           agent_data, add_instance_tags=False))

        # Agent Integration + relation to Agent
        agent_integration_external_id = Identifiers.create_integration_identifier(datadog_agent.get_hostname(),
                                                                                  instance_type)
        agent_integration_data = {
            "name": "{}:{}".format(datadog_agent.get_hostname(), instance_type), "integration": instance_type,
            "hostname": datadog_agent.get_hostname(), "tags": [
                "hostname:{}".format(datadog_agent.get_hostname()), "integration-type:{}".format(instance_type)
            ]
        }
        if datadog_agent.get_clustername():
            agent_integration_data["cluster"] = datadog_agent.get_clustername()

        conditions = {"host": datadog_agent.get_hostname(), "tags.integration-type": instance_type}
        service_check_stream = ServiceCheckStream("Service Checks", conditions=conditions)
        service_check = ServiceCheckHealthChecks.service_check_health(service_check_stream.identifier,
                                                                      "Integration Health")
        topology.submit_component(self, check_id, default_integration_instance.to_dict(), agent_integration_external_id,
                                  "agent-integration", self._map_component_data(agent_integration_external_id,
                                                                                "agent-integration",
                                                                                integration_instance,
                                                                                agent_integration_data,
                                                                                [service_check_stream], [service_check],
                                                                                add_instance_tags=False)
                                  )
        topology.submit_relation(self, check_id, default_integration_instance.to_dict(), agent_external_id,
                                 agent_integration_external_id, "runs",
                                 self._map_relation_data(agent_external_id, agent_integration_external_id, "runs", {}))

        # Agent Integration Instance + relation to Agent Integration
        agent_integration_instance_name = "{}:{}".format(instance_type, instance_url)
        agent_integration_instance_external_id = Identifiers.create_integration_instance_identifier(
            datadog_agent.get_hostname(), instance_type, instance_url
        )
        agent_integration_instance_data = {
            "name": agent_integration_instance_name, "integration": instance_type,
            "hostname": datadog_agent.get_hostname(),
            "tags": [
                "hostname:{}".format(datadog_agent.get_hostname())
            ]
        }

        if datadog_agent.get_clustername():
            agent_integration_instance_data["cluster"] = datadog_agent.get_clustername()

        conditions = {"host": datadog_agent.get_hostname(), "tags.integration-type": instance_type,
                      "tags.integration-url": instance_url}
        service_check_stream = ServiceCheckStream("Service Checks", conditions=conditions)
        service_check = ServiceCheckHealthChecks.service_check_health(service_check_stream.identifier,
                                                                      "Integration Instance Health")
        topology.submit_component(self, check_id, default_integration_instance.to_dict(),
                                  agent_integration_instance_external_id, "agent-integration-instance",
                                  self._map_component_data(agent_integration_instance_external_id,
                                                           "agent-integration-instance",
                                                           integration_instance, agent_integration_instance_data,
                                                           [service_check_stream], [service_check])
                                  )
        topology.submit_relation(self, check_id, default_integration_instance.to_dict(), agent_integration_external_id,
                                 agent_integration_instance_external_id, "has",
                                 self._map_relation_data(agent_integration_external_id,
                                                         agent_integration_instance_external_id, "has", {}))

    def validate_event(self, event):
        """
        Validates the event against the Event schematic model to make sure that all the expected values are provided
        and are the correct type
        `event` the event that will be validated against the Event schematic model.
        """
        # sent in as Event, validate to make sure it's correct
        if isinstance(event, Event):
            event.validate()
        # sent in as dictionary, convert to Event and validate to make sure it's correct
        elif isinstance(event, dict):
            _event = Event(event, strict=False)  # strict=False ignores extra fields provided by nagios
            _event.validate()
            event = _event
        elif not isinstance(event, Event):
            AgentCheckBase._raise_unexpected_type("event", event, "Dictionary or Event")

    def _submit_metric(self, mtype, name, value, tags=None, hostname=None, device_name=None):
        pass

    def _submit_raw_metrics_data(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        pass

    def raw(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        self._submit_raw_metrics_data(name, value, tags, hostname, device_name, timestamp)

    def gauge(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.GAUGE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def count(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.COUNT, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def monotonic_count(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.MONOTONIC_COUNT, name, value, tags=tags, hostname=hostname,
                            device_name=device_name)

    def rate(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.RATE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def histogram(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.HISTOGRAM, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def historate(self, name, value, tags=None, hostname=None, device_name=None):
        self._submit_metric(aggregator.HISTORATE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def increment(self, name, value=1, tags=None, hostname=None, device_name=None):
        self._log_deprecation('increment')
        self._submit_metric(aggregator.COUNTER, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def decrement(self, name, value=-1, tags=None, hostname=None, device_name=None):
        self._log_deprecation('increment')
        self._submit_metric(aggregator.COUNTER, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def _log_deprecation(self, deprecation_key):
        """
        Logs a deprecation notice at most once per AgentCheck instance, for the pre-defined `deprecation_key`
        """
        if not self._deprecations[deprecation_key][0]:
            self.log.warning(self._deprecations[deprecation_key][1])
            self._deprecations[deprecation_key][0] = True

    def get_warnings(self):
        """
        Return the list of warnings messages to be displayed in the info page
        """
        warnings = self.warnings
        self.warnings = []
        return warnings

    def _get_requests_proxy(self):
        no_proxy_settings = {
            'http': None,
            'https': None,
            'no': [],
        }

        # First we read the proxy configuration from datadog.conf
        proxies = self.agentConfig.get('proxy', datadog_agent.get_config('proxy'))
        if proxies:
            proxies = proxies.copy()

        # requests compliant dict
        if proxies and 'no_proxy' in proxies:
            proxies['no'] = proxies.pop('no_proxy')

        return proxies if proxies else no_proxy_settings

    # TODO collect all errors instead of the first one
    def _sanitize(self, field, context=None):
        """
        Fixes encoding and strips empty elements.
        :param field: Field can be of the following types: str, dict, list, set
        :param context: Context for error message.
        :return:
        """
        if isinstance(field, text_type):
            try:
                fixed_value = to_string(field)
            except UnicodeError as e:
                self.log.warning("Error while encoding unicode to string: '{0}', at {1}".format(field, context))
                raise e
            return fixed_value
        elif isinstance(field, dict):
            self._ensure_string_only_keys(field)
            field = {k: v for k, v in iteritems(field) if self._is_not_empty(v)}
            for key, value in list(iteritems(field)):
                field[key] = self._sanitize(value, "key '{0}' of dict".format(key))
        elif isinstance(field, list):
            self._ensure_homogeneous_list(field)
            field = [element for element in field if self._is_not_empty(element)]
            for i, element in enumerate(field):
                field[i] = self._sanitize(element, "index '{0}' of list".format(i))
        elif isinstance(field, set):
            # we convert a set to a list so we can update it in place
            # and then at the end we turn the list back to a set
            encoding_list = [element for element in list(field) if self._is_not_empty(element)]
            self._ensure_homogeneous_list(encoding_list)
            for i, element in enumerate(encoding_list):
                encoding_list[i] = self._sanitize(element, "element of set")
            field = set(encoding_list)
        return field

    def _is_not_empty(self, field):
        """
        _is_not_empty checks whether field contains "interesting" or is not None and returns true
        `field` the value to check
        """
        # for string types we don't want to keep the zero '' values
        if isinstance(field, string_types):
            if field:
                return True
        # keep zero values in data set
        else:
            if field is not None:
                return True

        return False

    def _ensure_string_only_keys(self, dictionary):
        """
        _ensure_string_only_keys checks whether all the keys of a dictionary are strings (and / or text_type).
        StackState only supports dictionaries with string keys. The conversion of text_type will happen in the _sanitize
        function using to_string(field).
        """
        type_list = [type(element) for element in iterkeys(dictionary)]
        type_set = set(type_list)

        # if the type_set is a subset of str and text_type return - We allow string + text_type as keys in a dictionary.
        # The conversion of text_type will happen in the _sanitize function using to_string(field).
        # <= is the subset operation on python sets.
        if type_set <= {str, text_type}:
            return

        raise TypeError("Dictionary: {0} contains keys which are not string or {1}: {2}"
                        .format(dictionary, text_type, type_set))

    def _ensure_homogeneous_list(self, list):
        """
        _ensure_homogeneous_list checks whether all values of a list or set are of the same type. StackState only
        supports homogeneous lists.
        """
        type_list = [type(element) for element in list]
        type_set = set(type_list)

        # exception rule - we allow string + text_type types together. The conversion of text_type will happen in the
        # _sanitize function using to_string(field). If the list only contains string type or text type the if condition
        # below will not trigger and the list is considered homogeneous. If a different combination exists (str, int)
        # then it fails as expected.
        if type_set == {str, text_type}:
            return

        if len(type_set) > 1:
            raise TypeError("List: {0}, is not homogeneous, it contains the following types: {1}"
                            .format(list, type_set))

    def get_check_state_path(self):
        """
        get_check_state_path returns the path where the check state is stored. By default the check configuration
        location will be used. If state_location is set in the check configuration that will be used instead.
        """
        state_location = self.instance.get("state_location", self.get_agent_conf_d_path())

        return "{}.d".format(os.path.join(state_location, self.name))

    def get_check_config_path(self):
        return "{}.d".format(os.path.join(self.get_agent_conf_d_path(), self.name))

    def get_agent_conf_d_path(self):
        return self.get_config("confd_path")

    @staticmethod
    def get_config(key):
        return datadog_agent.get_config(key)


class __AgentCheckPy3(AgentCheckBase):
    def __init__(self, *args, **kwargs):
        AgentCheckBase.__init__(self, *args, **kwargs)
        """
        args: `name`, `init_config`, `agentConfig` (deprecated), `instances`
        """
        self._deprecations = {
            'increment': [
                False,
                (
                    'DEPRECATION NOTICE: `AgentCheck.increment`/`AgentCheck.decrement` are deprecated, please '
                    'use `AgentCheck.gauge` or `AgentCheck.count` instead, with a different metric name'
                ),
            ],
            'device_name': [
                False,
                (
                    'DEPRECATION NOTICE: `device_name` is deprecated, please use a `device:` '
                    'tag in the `tags` list instead'
                ),
            ],
            'in_developer_mode': [
                False,
                'DEPRECATION NOTICE: `in_developer_mode` is deprecated, please stop using it.',
            ],
            'no_proxy': [
                False,
                (
                    'DEPRECATION NOTICE: The `no_proxy` config option has been renamed '
                    'to `skip_proxy` and will be removed in a future release.'
                ),
            ],
            'source_type_name': [
                False,
                "DEPRECATION NOTICE: The `source_type_name` event parameters has been deprecated "
                "in favour of `event_type` and will be removed in a future release.",
            ],
        }
        self.set_metric_limits()

    # TODO(olivier): implement service_metadata if it's worth it
    def service_metadata(self, meta_name, value):
        pass

    def check(self, instance):
        raise NotImplementedError

    def _submit_metric(self, mtype, name, value, tags=None, hostname=None, device_name=None):
        if value is None:
            # ignore metric sample
            return

        tags = self._normalize_tags_type(tags, device_name, name)
        if hostname is None:
            hostname = ''

        if self.metric_limiter:
            if mtype in ONE_PER_CONTEXT_METRIC_TYPES:
                # Fast path for gauges, rates, monotonic counters, assume one set of tags per call
                if self.metric_limiter.is_reached():
                    return
            else:
                # Other metric types have a legit use case for several calls per set of tags, track unique sets of tags
                context = self._context_uid(mtype, name, tags, hostname)
                if self.metric_limiter.is_reached(context):
                    return

        try:
            value = float(value)
        except ValueError:
            err_msg = (
                'Metric: {} has non float value: {}. Only float values can be submitted as metrics.'.format(name, value)
            )
            if using_stub_aggregator:
                raise ValueError(err_msg)
            self.warning(err_msg)
            return

        aggregator.submit_metric(self, self.check_id, mtype, ensure_unicode(name), value, tags, hostname)

    def _submit_raw_metrics_data(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        tags = self._normalize_tags_type(tags, device_name, name)

        if timestamp is None:
            self.warning('Ignoring raw metric, timestamp is empty')
            return

        if hostname is None:
            hostname = ''

        telemetry.submit_raw_metrics_data(self, self.check_id, ensure_unicode(name), value, tags, hostname, timestamp)

    def service_check(self, name, status, tags=None, hostname=None, message=None):
        tags = self._normalize_tags_type(tags)
        if hostname is None:
            hostname = ''
        if message is None:
            message = ''
        else:
            message = ensure_unicode(message)

        instance = self._get_instance_key()
        aggregator.submit_service_check(self, self.check_id, ensure_unicode(name), status, tags + instance.tags(),
                                        hostname, message)

    def event(self, event):
        self.validate_event(event)

        # Enforce types of some fields, considerably facilitates handling in go bindings downstream
        try:
            event = self._sanitize(event)
        except (UnicodeError, TypeError):
            return

        if event.get('tags'):
            event['tags'] = self._normalize_tags_type(event['tags'])
        if event.get('timestamp'):
            event['timestamp'] = int(event['timestamp'])
        if event.get('aggregation_key'):
            event['aggregation_key'] = ensure_unicode(event['aggregation_key'])
        # TODO: This is a workaround as the Go agent doesn't correctly map event_type for normal events. Clean this up
        if event.get('event_type'):
            # map event_type as source_type_name for go agent
            event['source_type_name'] = ensure_unicode(event['event_type'])
        elif event.get('source_type_name'):
            self._log_deprecation("source_type_name")
            # if we have the source_type_name and not an event_type map the source_type_name as the event_type
            event['event_type'] = ensure_unicode(event['source_type_name'])

        if 'context' in event:
            telemetry.submit_topology_event(self, self.check_id, event)
        else:
            aggregator.submit_event(self, self.check_id, event)

    def _normalize_tags_type(self, tags, device_name=None, metric_name=None):
        """
        Normalize tags contents and type:
        - append `device_name` as `device:` tag
        - normalize tags type
        - doesn't mutate the passed list, returns a new list
        """
        normalized_tags = []

        if device_name:
            self._log_deprecation('device_name')
            normalized_tags.append('device:{}'.format(ensure_unicode(device_name)))

        if tags is not None:
            for tag in tags:
                if not isinstance(tag, str):
                    try:
                        tag = tag.decode('utf-8')
                    except UnicodeError:
                        self.log.warning(
                            'Error decoding tag `{}` as utf-8 for metric `{}`, ignoring tag'.format(tag, metric_name)
                        )
                        continue

                normalized_tags.append(tag)

        return normalized_tags

    def warning(self, warning_message):
        warning_message = ensure_unicode(warning_message)

        frame = inspect.currentframe().f_back
        lineno = frame.f_lineno
        # only log the last part of the filename, not the full path
        filename = basename(frame.f_code.co_filename)

        self.log.warning(warning_message, extra={'_lineno': lineno, '_filename': filename})
        self.warnings.append(warning_message)

    def run(self):
        return self._check_run_base('')


class __AgentCheckPy2(AgentCheckBase):
    """
    The base class for any Agent based integrations
    """

    def __init__(self, *args, **kwargs):
        AgentCheckBase.__init__(self, *args, **kwargs)
        """
        args: `name`, `init_config`, `agentConfig` (deprecated), `instances`
        """
        self.check_id = b''

        self._deprecations = {
            'increment': [
                False,
                "DEPRECATION NOTICE: `AgentCheck.increment`/`AgentCheck.decrement` are deprecated, please use "
                "`AgentCheck.gauge` or `AgentCheck.count` instead, with a different metric name",
            ],
            'device_name': [
                False,
                "DEPRECATION NOTICE: `device_name` is deprecated, please use a `device:` "
                "tag in the `tags` list instead",
            ],
            'in_developer_mode': [
                False,
                "DEPRECATION NOTICE: `in_developer_mode` is deprecated, please stop using it.",
            ],
            'no_proxy': [
                False,
                "DEPRECATION NOTICE: The `no_proxy` config option has been renamed "
                "to `skip_proxy` and will be removed in a future release.",
            ],
            'source_type_name': [
                False,
                "DEPRECATION NOTICE: The `source_type_name` event parameters has been deprecated "
                "in favour of `event_type` and will be removed in a future release.",
            ],
        }

        self.set_metric_limits()

    # TODO(olivier): implement service_metadata if it's worth it
    def service_metadata(self, meta_name, value):
        pass

    def check(self, instance):
        raise NotImplementedError

    def _submit_metric(self, mtype, name, value, tags=None, hostname=None, device_name=None):
        if value is None:
            # ignore metric sample
            return

        tags = self._normalize_tags_type(tags, device_name, name)
        if hostname is None:
            hostname = b''

        if self.metric_limiter:
            if mtype in ONE_PER_CONTEXT_METRIC_TYPES:
                # Fast path for gauges, rates, monotonic counters, assume one set of tags per call
                if self.metric_limiter.is_reached():
                    return
            else:
                # Other metric types have a legit use case for several calls per set of tags, track unique sets of tags
                context = self._context_uid(mtype, name, tags, hostname)
                if self.metric_limiter.is_reached(context):
                    return
        try:
            value = float(value)
        except ValueError:
            err_msg = (
                "Metric: {} has non float value: {}. "
                "Only float values can be submitted as metrics.".format(repr(name), repr(value))
            )
            if using_stub_aggregator:
                raise ValueError(err_msg)
            self.warning(err_msg)
            return

        aggregator.submit_metric(self, self.check_id, mtype, ensure_string(name), value, tags, hostname)

    def _submit_raw_metrics_data(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        tags = self._normalize_tags_type(tags, device_name, name)

        if timestamp is None:
            self.warning('Ignoring raw metric, timestamp is empty')
            return

        if hostname is None:
            hostname = b''

        telemetry.submit_raw_metrics_data(self, self.check_id, ensure_unicode(name), value, tags, hostname, timestamp)

    def service_check(self, name, status, tags=None, hostname=None, message=None):
        tags = self._normalize_tags_type(tags)
        if hostname is None:
            hostname = b''
        if message is None:
            message = b''
        else:
            message = ensure_string(message)

        integration_instance = self._get_instance_key()
        tags_bytes = list(map(lambda t: ensure_string(t), integration_instance.tags()))
        aggregator.submit_service_check(self, self.check_id, ensure_string(name), status,
                                        tags + tags_bytes, hostname, message)

    def event(self, event):
        self.validate_event(event)
        # Enforce types of some fields, considerably facilitates handling in go bindings downstream
        try:
            event = self._sanitize(event)
        except (UnicodeError, TypeError):
            return

        if event.get('tags'):
            event['tags'] = self._normalize_tags_type(event['tags'])
        if event.get('timestamp'):
            event['timestamp'] = int(event['timestamp'])
        if event.get('aggregation_key'):
            event['aggregation_key'] = ensure_string(event['aggregation_key'])
        # TODO: This is a workaround as the Go agent doesn't correctly map event_type for normal events. Clean this up
        if event.get('event_type'):
            # map event_type as source_type_name for go agent
            event['source_type_name'] = ensure_string(event['event_type'])
        elif event.get('source_type_name'):
            self._log_deprecation("source_type_name")
            # if we have the source_type_name and not an event_type map the source_type_name as the event_type
            event['event_type'] = ensure_string(event['source_type_name'])

        if 'context' in event:
            telemetry.submit_topology_event(self, self.check_id, event)
        else:
            aggregator.submit_event(self, self.check_id, event)

        return event

    def _normalize_tags_type(self, tags, device_name=None, metric_name=None):
        """
        Normalize tags contents and type:
        - append `device_name` as `device:` tag
        - normalize tags type
        - doesn't mutate the passed list, returns a new list
        """
        normalized_tags = []
        if device_name:
            self._log_deprecation("device_name")
            device_tag = self._to_bytes("device:{}".format(device_name))
            if device_tag is None:
                self.log.warning(
                    'Error encoding device name `{}` to utf-8 for metric `{}`, ignoring tag'.format(
                        repr(device_name), repr(metric_name)
                    )
                )
            else:
                normalized_tags.append(device_tag)

        if tags is not None:
            for tag in tags:
                encoded_tag = self._to_bytes(tag)
                if encoded_tag is None:
                    self.log.warning(
                        'Error encoding tag `{}` to utf-8 for metric `{}`, ignoring tag'.format(
                            repr(tag), repr(metric_name)
                        )
                    )
                    continue
                normalized_tags.append(encoded_tag)

        return normalized_tags

    def _to_bytes(self, data):
        """
        Normalize a text data to bytes (type `bytes`) so that the go bindings can
        handle it easily.
        """
        # TODO: On Python 3, move this `if` line to the `except` branch
        # as the common case will indeed no longer be bytes.
        if not isinstance(data, bytes):
            try:
                return data.encode('utf-8')
            except Exception:
                return None

        return data

    def warning(self, warning_message):
        warning_message = ensure_string(warning_message)

        frame = inspect.currentframe().f_back
        lineno = frame.f_lineno
        filename = frame.f_code.co_filename
        # only log the last part of the filename, not the full path
        filename = basename(filename)

        self.log.warning(warning_message, extra={'_lineno': lineno, '_filename': filename})
        self.warnings.append(warning_message)

    def run(self):
        return self._check_run_base(b'')


if PY3:
    AgentCheck = __AgentCheckPy3
    del __AgentCheckPy2
else:
    AgentCheck = __AgentCheckPy2
    del __AgentCheckPy3
