# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import copy
import inspect
import json
import logging
import os
import re
import traceback
import unicodedata
import sys
import yaml

from collections import defaultdict
from functools import reduce
from os.path import basename
from stackstate_checks.base.utils.validations_utils import CheckBaseModel
from pydantic import ValidationError
from six import PY3, iteritems, iterkeys, text_type, string_types, integer_types
from typing import Any, Set, Dict, Sequence, List, Optional, Union, AnyStr, TypeVar
from ..utils.health_api import HealthApiCommon

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
from ..utils.health_api import HealthApi
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

    def to_string(self):
        return "{}_{}".format(self.type, self.url)

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
        if isinstance(other, AgentIntegrationInstance):
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

_SanitazableType = TypeVar('_SanitazableType', str, Dict[str, Any], List, Set)
_InstanceType = TypeVar('_InstanceType', CheckBaseModel, Dict[str, Any])
_EventType = TypeVar('_EventType', CheckBaseModel, Dict[str, Any])


class AgentCheck(HealthApiCommon):
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
    INSTANCE_SCHEMA: CheckBaseModel | None = None

    """
    STATE_FIELD_NAME is used to determine to which key the check state should be set, defaults to `state`
    """
    STATE_FIELD_NAME = 'state'

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        """
        - **name** (_str_) - the name of the check
        - **init_config** (_dict_) - the `init_config` section of the configuration.
        - **agentConfig** (_dict_) - deprecated
        - **instance** (_List[dict]_) - a one-element list containing the instance options from the
                configuration file (a list is used to keep backward compatibility with
                older versions of the Agent).
        """
        self.check_id = to_string(b'')
        self.metrics = defaultdict(list)  # type: Dict[str, List[str]]
        self.name = kwargs.get('name', '')
        self.init_config = kwargs.get('init_config', {})
        self.agentConfig = kwargs.get('agentConfig', {})
        self.warnings = []  # type: List[str]
        self.metric_limiter = None  # type: Optional[Limiter]
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
        self.cluster_name = AgentCheck.get_cluster_name()

        self.log = logging.getLogger('{}.{}'.format(__name__, self.name))
        if using_stub_aggregator:
            self.log.warning("Using stub aggregator api")
        if using_stub_topology:
            self.log.warning("Using stub topology api")
        if using_stub_telemetry:
            self.log.warning("Using stub telemetry api")
        self.state_manager = StateManager(self.log)
        # Set proxy settings
        self.proxies = self._get_requests_proxy()
        if not self.init_config:
            self._use_agent_proxy = True
        else:
            self._use_agent_proxy = is_affirmative(self.init_config.get('use_agent_proxy', True))

        self.default_integration_http_timeout = float(self.agentConfig.get('default_integration_http_timeout', 9))

        # Will be initialized as part of the check, to allow for proper error reporting there if initialization fails
        self.health = None  # type: Optional[HealthApi]

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
        }  # type: Dict[str, List[Any]]

        self.set_metric_limits()

    def run(self):
        # type: () -> str
        """
        Runs check.
        """
        default_result = to_string(b'')
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
        # type: (Any, bool) -> None
        """
        commit_state can be used to immediately set (and optionally flush) state in the agent, instead of first
        completing
        the check
        """
        self.state_manager.set_state(self._get_state_descriptor(), state, flush)

    def set_metric_limits(self):
        # type: () -> None
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
        # type: () -> StateDescriptor
        integration_instance = self._get_instance_key()
        instance_key = to_string(
            self.normalize("instance.{}.{}".format(integration_instance.type, integration_instance.url),
                           extra_disallowed_chars=b":")
        )

        return StateDescriptor(instance_key, self.get_check_state_path())

    @staticmethod
    def get_cluster_name():
        # type: () -> str
        """
        returns the cluster name if the check is running in Kubernetes / OpenShift
        """
        return datadog_agent.get_clustername()

    @staticmethod
    def get_hostname():
        # type: () -> str
        """
        returns the hostname
        """
        return datadog_agent.get_hostname()

    @staticmethod
    def load_config(yaml_str):
        # type: (str) -> Any
        """
        Convenience wrapper to ease programmatic use of this class from the C API.
        """
        return yaml.safe_load(yaml_str)

    @property
    def in_developer_mode(self):
        # type: () -> bool
        self._log_deprecation('in_developer_mode')
        return False

    @staticmethod
    def _context_uid(mtype, name, tags=None, hostname=None):
        # type: (int, str, Sequence[str], str) -> str
        return '{}-{}-{}-{}'.format(mtype, name, tags if tags is None else hash(frozenset(tags)), hostname)

    @staticmethod
    def _check_not_none(argument_name, value):
        # type: (str, str) -> None
        if value is None:
            raise ValueError("Got None value for argument {}".format(argument_name))

    @staticmethod
    def _check_is_string(argument_name, value):
        # type: (str, str) -> None
        AgentCheck._check_not_none(argument_name, value)
        if not isinstance(value, string_types):
            AgentCheck._raise_unexpected_type(argument_name, value, "string")

    @staticmethod
    def _raise_unexpected_type(argument_name, value, expected):
        # type: (str, Any, str) -> None
        raise ValueError("Got unexpected {} for argument {}, expected {}".format(type(value), argument_name, expected))

    @staticmethod
    def _check_struct_value(argument_name, value):
        # type: (str, Any) -> None
        if value is None or isinstance(value, string_types) or isinstance(value, integer_types) or \
                isinstance(value, float) or isinstance(value, bool):
            return
        elif isinstance(value, dict):
            for k in value:
                AgentCheck._check_struct_value("{}.{}".format(argument_name, k), value[k])
        elif isinstance(value, list):
            for idx, val in enumerate(value):
                AgentCheck._check_struct_value("{}[{}]".format(argument_name, idx), val)
        else:
            AgentCheck._raise_unexpected_type(argument_name, value, "string, int, dictionary, list or None value")

    @staticmethod
    def _check_struct(argument_name, value):
        # type: (str, Any) -> None
        if isinstance(value, dict):
            AgentCheck._check_struct_value(argument_name, value)
        else:
            AgentCheck._raise_unexpected_type(argument_name, value, "dictionary or None value")

    def _get_instance_schema(self, instance):
        # type: (Dict[str, Any]) -> _InstanceType
        """
        If this check has a instance schema defined, cast it into that type and validate it.
        """
        check_instance = instance

        if self.INSTANCE_SCHEMA:
            try:
                check_instance = self.INSTANCE_SCHEMA(**instance)
            except ValidationError as e:
                print("Error validating instance: ", e)
                raise e

        return check_instance

    def get_instance_key(self, instance):
        # type: (_InstanceType) -> _TopologyInstanceBase
        """Integration checks can override this based on their needs.

        :param: instance: AgentCheck instance
        :return: a class extending _TopologyInstanceBase
        """
        return NoIntegrationInstance()

    def _get_instance_key(self):
        # type: () -> _TopologyInstanceBase
        check_instance = self._get_instance_schema(self.instance)

        value = self.get_instance_key(check_instance)

        if value is None:
            AgentCheck._raise_unexpected_type("get_instance_key()", "None", "dictionary")
        if not isinstance(value, (TopologyInstance, AgentIntegrationInstance, NoIntegrationInstance)):
            AgentCheck._raise_unexpected_type("get_instance_key()",
                                              value,
                                              "TopologyInstance, AgentIntegrationInstance or "
                                              "DefaultIntegrationInstance")
        # Convert unicode to string if the url is a unicode
        if isinstance(value.url, text_type):
            value.url = str(value.url)

        if not isinstance(value.type, str):
            raise ValueError("Instance requires a 'type' field of type 'string'")
        if not isinstance(value.url, str):
            raise ValueError("Instance requires a 'url' field of type 'string'")

        return value

    def _get_instance_key_dict(self):
        # type: () -> Dict[str, Any]
        return self._get_instance_key().to_dict()

    def get_instance_proxy(self, instance, uri, proxies=None):
        # type: (_InstanceType, str, Optional[Dict[str, Any]]) -> Dict[str, Any]
        proxies = proxies if proxies is not None else self.proxies.copy()

        deprecated_skip = instance.get('no_proxy', None)
        skip = (is_affirmative(instance.get('skip_proxy', not self._use_agent_proxy)) or
                is_affirmative(deprecated_skip))

        if deprecated_skip is not None:
            self._log_deprecation('no_proxy')

        return config_proxy_skip(proxies, uri, skip)

    # TODO(olivier): implement service_metadata if it's worth it
    def service_metadata(self, meta_name, value):
        pass

    def check(self, instance):
        # type: (_InstanceType) -> None
        raise NotImplementedError

    def warning(self, warning_message):
        # type: (str) -> None
        """ Log a warning message and display it in the Agent's status page.
        - **warning_message** (_str_): the warning message.
        """
        warning_message = to_string(warning_message)

        lineno = None
        filename = None
        cur_frame = inspect.currentframe()
        if cur_frame and cur_frame.f_back:
            frame = cur_frame.f_back
            lineno = frame.f_lineno
            # only log the last part of the filename, not the full path
            filename = basename(frame.f_code.co_filename)

        self.log.warning(warning_message, extra={'_lineno': lineno, '_filename': filename})
        self.warnings.append(warning_message)

    def normalize(self, metric, prefix=None, fix_case=False, extra_disallowed_chars=None):
        # type: (AnyStr, AnyStr, bool, Optional[bytes]) -> bytes
        """
        Turn a metric into a well-formed metric name
        prefix.b.c
        :param metric The metric name to normalize
        :param prefix A prefix to add to the normalized name, default None
        :param fix_case A boolean, indicating whether to make sure that the metric name returned is in "snake_case"
        :param extra_disallowed_chars Custom characters for regex
        """
        if isinstance(metric, bytes):
            metricb = metric
        else:
            metricb = unicodedata.normalize('NFKD', metric).encode('ascii', 'ignore')

        prefixb = ensure_string(prefix)
        if fix_case:
            name = self.convert_to_underscore_separated(metricb)
            if prefix is not None:
                prefixb = self.convert_to_underscore_separated(prefix)
        elif extra_disallowed_chars:
            name = re.sub(br"[,\+\*\-/()\[\]{}\s" + extra_disallowed_chars + br"]", b"_", metricb)
        else:
            name = re.sub(br"[,\+\*\-/()\[\]{}\s]", b"_", metricb)
        # Eliminate multiple _
        name = re.sub(br"__+", b"_", name)
        # Don't start/end with _
        name = re.sub(br"^_", b"", name)
        name = re.sub(br"_$", b"", name)
        # Drop ._ and _.
        name = re.sub(br"\._", b".", name)
        name = re.sub(br"_\.", b".", name)

        if prefixb is not None:
            return prefixb + b"." + name
        else:
            return ensure_string(name)

    FIRST_CAP_RE = re.compile(br'(.)([A-Z][a-z]+)')
    ALL_CAP_RE = re.compile(br'([a-z0-9])([A-Z])')
    METRIC_REPLACEMENT = re.compile(br'([^a-zA-Z0-9_.]+)|(^[^a-zA-Z]+)')
    DOT_UNDERSCORE_CLEANUP = re.compile(br'_*\._*')

    def convert_to_underscore_separated(self, name):
        # type: (AnyStr) -> bytes
        """
        Convert from CamelCase to camel_case
        And substitute illegal metric characters
        """
        metric_name = self.FIRST_CAP_RE.sub(br'\1_\2', ensure_string(name))
        metric_name = self.ALL_CAP_RE.sub(br'\1_\2', metric_name).lower()
        metric_name = self.METRIC_REPLACEMENT.sub(br'_', metric_name)
        return self.DOT_UNDERSCORE_CLEANUP.sub(br'.', metric_name).strip(b'_')

    def component(self, id, type, data, streams=None, checks=None):
        # type: (str, str, Dict, Optional[List], Optional[List]) -> Optional[Dict[str, Any]]
        integration_instance = self._get_instance_key()
        try:
            fixed_data = self._sanitize(data)
            fixed_streams = self._sanitize(streams) if streams is not None else None
            fixed_checks = self._sanitize(checks) if checks is not None else None
        except (UnicodeError, TypeError):
            return None
        data = self._map_component_data(id, type, integration_instance, fixed_data, fixed_streams, fixed_checks)
        topology.submit_component(self, self.check_id, self._get_instance_key_dict(), id, type, data)
        return {"id": id, "type": type, "data": data}

    def _map_component_data(self, id, type, integration_instance, data, streams=None, checks=None,
                            add_instance_tags=True):
        # type: (str, str, _TopologyInstanceBase, Dict, Optional[List], Optional[List], bool) -> Dict
        AgentCheck._check_is_string("id", id)
        AgentCheck._check_is_string("type", type)
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
        # type: (str, str, str, Dict[str, Any], Optional[List], Optional[List]) -> Optional[Dict[str, Any]]
        try:
            fixed_data = self._sanitize(data)
            fixed_streams = self._sanitize(streams) if streams is not None else None
            fixed_checks = self._sanitize(checks) if checks is not None else None
        except (UnicodeError, TypeError):
            return None
        data = self._map_relation_data(source, target, type, fixed_data, fixed_streams, fixed_checks)
        topology.submit_relation(self, self.check_id, self._get_instance_key_dict(), source, target, type, data)
        return {"source_id": source, "target_id": target, "type": type, "data": data}

    def delete(self, identifier):
        # type: (str) -> str
        AgentCheck._check_is_string("identifier", identifier)
        topology.submit_delete(self, self.check_id, self._get_instance_key_dict(), identifier)
        return identifier

    def _map_stackstate_tags_and_instance_config(self, data):
        # type: (Dict[str, Any]) -> Dict[str, Any]
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
        single_identifier_tag = self._get_config_or_tag_value(data, 'stackstate-identifier', False)
        if isinstance(single_identifier_tag, str):
            identifiers = identifiers + [single_identifier_tag]

        # Only apply identifiers if we found any
        if len(identifiers) > 0:
            data["identifiers"] = identifiers

        # Attempt to map stackstate-*** tags and configs
        data = self._move_data_with_config_or_tags(data, 'stackstate-layer', 'layer')
        data = self._move_data_with_config_or_tags(data, 'stackstate-environment', 'environments', return_array=True)
        data = self._move_data_with_config_or_tags(data, 'stackstate-domain', 'domain')

        return data

    @staticmethod
    def split_on_commas_and_spaces(content):
        # type: (Any) -> List[str]
        """Regex function used to split a string on commas and/or spaces.
        """
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

    def _get_config_or_tag_value(self, data, key, return_array=False, default=None):
        # type: (Dict[str, Any], str, bool, str) -> Any

        # Get the first instance and create a deep copy
        instance = self.instances[0] if self.instances is not None and len(self.instances) else {}
        check_instance = copy.deepcopy(instance)

        # Extract or create the tags
        tags = data.get('tags', [])

        # Attempt to find the tag and map its value to a object inside data
        find_tag = next((tag for tag in tags if (key + ':' in tag)), None)
        if isinstance(find_tag, str) and find_tag.index(":") > 0:
            result = [find_tag.split(key + ':')[1]] if return_array is True else find_tag.split(key + ':')[1]
            # Remove the tag from tags if found
            tags.remove(find_tag)
            return result

        elif key in check_instance and isinstance(check_instance[key], str):
            result = [check_instance[key]] if return_array is True else check_instance[key]
            return result

        elif default is not None and isinstance(default, str):
            result = [default] if return_array is True else default
            return result

        return [] if return_array else None

    def _move_data_with_config_or_tags(self, data, target, origin, return_array=False, default=None):
        # type: (Dict[str, Any], str, str, bool, str) -> Dict[str, Any]
        """
        Generic mapping function for tags or config.
        Attempt to find if the target exists on a tag or config and map that to the origin value.
        There's an optional default value if required.
        Value override order: tags < config.yaml
        """
        value = self._get_config_or_tag_value(data, target, return_array, default)
        if value is not None and (not return_array or len(value) > 0):
            data[origin] = value
        return data

    def _map_relation_data(self, source, target, type, data, streams=None, checks=None):
        # type: (str, str, str, Dict[str, Any], Optional[List], Optional[List]) -> Dict[str, Any]
        AgentCheck._check_is_string("source", source)
        AgentCheck._check_is_string("target", target)
        AgentCheck._check_is_string("type", type)
        self._check_struct("data", data)
        if data is None:
            data = {}
        data = self._map_streams_and_checks(data, streams, checks)
        self._check_struct("data", data)
        return data

    @staticmethod
    def get_mapping_field_key(dictionary, keys, default=None):
        # type: (Dict[str, Any], str, str) -> Dict[str, Any]
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

    @staticmethod
    def _map_streams_and_checks(data, streams, checks):
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
        # type: () -> None
        topology.submit_start_snapshot(self, self.check_id, self._get_instance_key_dict())

    @deprecated(version='2.9.0', reason="Topology Snapshots is enabled by default for all TopologyInstance checks, "
                                        "to disable snapshots use TopologyInstance(type, url, with_snapshots=False) "
                                        "when overriding get_instance_key")
    def stop_snapshot(self):
        # type: () -> None
        topology.submit_stop_snapshot(self, self.check_id, self._get_instance_key_dict())

    def create_integration_instance(self):
        # type: () -> None
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

    @staticmethod
    def validate_event(event):
        # type: (_EventType) -> None
        """
        Validates the event against the Event schematic model to make sure that all the expected values are provided
        and are the correct type
        `event` the event that will be validated against the Event schematic model.
        """
        if isinstance(event, Event):
            return
        # sent in as dictionary, convert to Event and validate to make sure it's correct
        elif isinstance(event, dict):
            Event(**event)
        elif not isinstance(event, Event):
            AgentCheck._raise_unexpected_type("event", event, "Dictionary or Event")

    def _submit_metric(self, mtype, name, value, tags=None, hostname=None, device_name=None):
        # type: (int, str, float, Sequence[str], str, str) -> None
        if value is None:
            # ignore metric sample
            return

        tags = self._normalize_tags_type(tags, device_name, name)
        if hostname is None:
            hostname = to_string(b'')

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
                "Metric: {!r} has non float value: {!r}. "
                "Only float values can be submitted as metrics.".format(name, value)
            )
            if using_stub_aggregator:
                raise ValueError(err_msg)
            self.warning(err_msg)
            return

        aggregator.submit_metric(self, self.check_id, mtype, to_string(name), value, tags, hostname)

    def _submit_raw_metrics_data(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        # type: (str, float, Sequence[str], str, str, int) -> None
        tags = self._normalize_tags_type(tags, device_name, name)

        if timestamp is None:
            self.warning('Ignoring raw metric, timestamp is empty')
            return

        if hostname is None:
            hostname = to_string(b'')

        telemetry.submit_raw_metrics_data(self, self.check_id, ensure_unicode(name), value, tags, hostname, timestamp)

    def raw(self, name, value, tags=None, hostname=None, device_name=None, timestamp=None):
        # type: (str, float, Sequence[str], str, str, int) -> None
        self._submit_raw_metrics_data(name, value, tags, hostname, device_name, timestamp)

    def gauge(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample a gauge metric.

        **Parameters:**

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.GAUGE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def count(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample a raw count metric.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.COUNT, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def monotonic_count(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample an increasing counter metric.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.MONOTONIC_COUNT, name, value, tags=tags, hostname=hostname,
                            device_name=device_name)

    def rate(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample a point, with the rate calculated at the end of the check.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.RATE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def histogram(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample a histogram metric.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.HISTOGRAM, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def historate(self, name, value, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Sample a histogram based on rate metrics.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._submit_metric(aggregator.HISTORATE, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def increment(self, name, value=1, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Increment a counter metric.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._log_deprecation('increment')
        self._submit_metric(aggregator.COUNTER, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def decrement(self, name, value=-1, tags=None, hostname=None, device_name=None):
        # type: (str, float, Sequence[str], str, str) -> None
        """Decrement a counter metric.

        - **name** (_str_) - the name of the metric
        - **value** (_float_) - the value for the metric
        - **tags** (_List[str]_) - a list of tags to associate with this metric
        - **hostname** (_str_) - a hostname to associate with this metric. Defaults to the current host.
        - **device_name** (_str_) - **deprecated** add a tag in the form `device:<device_name>` to the `tags`
            list instead.
        """
        self._log_deprecation('increment')
        self._submit_metric(aggregator.COUNTER, name, value, tags=tags, hostname=hostname, device_name=device_name)

    def _log_deprecation(self, deprecation_key):
        # type: (str) -> None
        """
        Logs a deprecation notice at most once per AgentCheck instance, for the pre-defined `deprecation_key`
        """
        if not self._deprecations[deprecation_key][0]:
            self.log.warning(self._deprecations[deprecation_key][1])
            self._deprecations[deprecation_key][0] = True

    def get_warnings(self):
        # type: () -> List[str]
        """
        Return the list of warnings messages to be displayed in the info page
        """
        warnings = self.warnings
        self.warnings = []
        return warnings

    def _get_requests_proxy(self):
        # type: () -> Dict[str, Any]
        no_proxy_settings = {
            'http': None,
            'https': None,
            'no': [],
        }  # type: Dict[str, Any]

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
        # type: (_SanitazableType, Optional[str]) -> _SanitazableType
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

    @staticmethod
    def _is_not_empty(field):
        # type: (Any) -> bool
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

    @staticmethod
    def _ensure_string_only_keys(dictionary):
        # type: (Dict[str, Any]) -> None
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
            return None

        raise TypeError("Dictionary: {0} contains keys which are not string or {1}: {2}"
                        .format(dictionary, text_type, type_set))

    @staticmethod
    def _ensure_homogeneous_list(list):
        # type: (List) -> None
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
            return None

        if len(type_set) > 1:
            raise TypeError("List: {0}, is not homogeneous, it contains the following types: {1}"
                            .format(list, sorted(str(x) for x in type_set)))

    def get_check_state_path(self):
        # type: () -> str
        """
        get_check_state_path returns the path where the check state is stored. By default, the check configuration
        location will be used. If state_location is set in the check configuration that will be used instead.
        """
        state_location = self.instance.get("state_location", self.get_agent_conf_d_path())

        return "{}.d".format(os.path.join(state_location, self.name))

    def get_check_config_path(self):
        # type: () -> str
        return "{}.d".format(os.path.join(self.get_agent_conf_d_path(), self.name))

    def get_agent_conf_d_path(self):
        # type: () -> str
        return self.get_config("confd_path")

    @staticmethod
    def get_config(key):
        # type: (str) -> str
        return datadog_agent.get_config(key)

    def _persistent_cache_id(self, key):
        # type: (str) -> str
        return '{}_{}'.format(self.check_id, key)

    def read_persistent_cache(self, key):
        # type: (str) -> str
        """Returns the value previously stored with `write_persistent_cache` for the same `key`.
        - **key** (_str_) - The key to retrieve
        """
        return datadog_agent.read_persistent_cache(self._persistent_cache_id(key))

    def write_persistent_cache(self, key, value):
        # type: (str, str) -> None
        """Stores `value` in a persistent cache for this check instance.
        The cache is located in a path where the agent is guaranteed to have read & write permissions. Namely in
            - `%ProgramData%\\Datadog\\run` on Windows.
            - `/opt/datadog-agent/run` everywhere else.
        The cache is persistent between agent restarts but will be rebuilt if the check instance configuration changes.
        - **key** (_str_) - Identifier used to build the filename
        - **value** (_str_) - Value to store
        """
        datadog_agent.write_persistent_cache(self._persistent_cache_id(key), value)

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
                    'Error encoding device name `{!r}` to utf-8 for metric `{!r}`, ignoring tag'.format(
                        device_name, metric_name
                    )
                )
            else:
                normalized_tags.append(to_string(device_tag))

        if tags is not None:
            for tag in tags:
                if PY3:
                    if not isinstance(tag, str):
                        try:
                            normalized_tag = tag.decode('utf-8')
                        except UnicodeError:
                            self.log.warning(
                                'Error decoding tag `{}` as utf-8 for metric `{}`, ignoring tag'.format(tag,
                                                                                                        metric_name)
                            )
                            continue
                    else:
                        normalized_tag = tag
                else:
                    normalized_tag = self._to_bytes(tag)
                    if normalized_tag is None:
                        self.log.warning(
                            'Error encoding tag `{!r}` to utf-8 for metric `{!r}`, ignoring tag'.format(tag,
                                                                                                        metric_name)
                        )
                        continue
                normalized_tags.append(normalized_tag)

        return normalized_tags

    @staticmethod
    def _to_bytes(data):
        """
        Normalize a text data to bytes (type `bytes`) so that the go bindings can
        handle it easily.
        """
        # TODO: On Python 3, move this `if` line to the `except` branch
        # as the common case will indeed no longer be bytes.
        if not isinstance(data, bytes):
            try:
                return data.encode('utf-8')
            except UnicodeError:
                return None

        return data

    def service_check(self, name, status, tags=None, hostname=None, message=None):
        # type: (str, int, List[str], str, str) -> None
        """Send the status of a service.
        - **name** (_str_) - the name of the service check
        - **status** (_int_) - a constant describing the service status.
        - **tags** (_List[str]_) - a list of tags to associate with this service check
        - **hostname** (_str_) - hostname, do we use this at anywhere?
        - **message** (_str_) - additional information or a description of why this status occurred.
        """
        if hostname is None:
            hostname = to_string(b'')
        if message is None:
            message = to_string(b'')
        else:
            message = to_string(message)

        integration_instance = self._get_instance_key()
        tags_bytes = list(map(lambda t: to_string(t), integration_instance.tags()))  # type: List[Union[str, bytes]]
        all_tags = self._normalize_tags_type(tags) + tags_bytes

        aggregator.submit_service_check(self, self.check_id, to_string(name), status,
                                        all_tags, hostname, message)

    def event(self, event):
        # type: (Dict[str, Any]) -> Optional[Dict[str, Any]]
        """Send an event.
        """
        self.validate_event(event)
        # Enforce types of some fields, considerably facilitates handling in go bindings downstream
        try:
            event = self._sanitize(event)
        except (UnicodeError, TypeError):
            return None

        if event.get('tags'):
            event['tags'] = self._normalize_tags_type(event['tags'])
        if event.get('timestamp'):
            event['timestamp'] = int(event['timestamp'])
        if event.get('aggregation_key'):
            event['aggregation_key'] = to_string(event['aggregation_key'])
        # TODO: This is a workaround as the Go agent doesn't correctly map event_type for normal events. Clean this up
        if event.get('event_type'):
            # map event_type as source_type_name for go agent
            event['source_type_name'] = to_string(event['event_type'])
        elif event.get('source_type_name'):
            self._log_deprecation("source_type_name")
            # if we have the source_type_name and not an event_type map the source_type_name as the event_type
            event['event_type'] = to_string(event['source_type_name'])

        if 'context' in event:
            telemetry.submit_topology_event(self, self.check_id, event)
        else:
            aggregator.submit_event(self, self.check_id, event)

        return event
