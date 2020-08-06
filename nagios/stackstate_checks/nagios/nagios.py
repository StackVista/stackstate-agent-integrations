# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import logging
import re
from collections import namedtuple

from pynag import Model

from stackstate_checks.base.utils.tailfile import TailFile
from stackstate_checks.checks import AgentCheck, TopologyInstance

EVENT_FIELDS = {
    'CURRENT HOST STATE': namedtuple('E_CurrentHostState', 'host, event_state, event_soft_hard, return_code, payload'),
    'CURRENT SERVICE STATE': namedtuple('E_CurrentServiceState',
                                        'host, check_name, event_state, event_soft_hard, return_code, payload'),
    'SERVICE ALERT': namedtuple('E_ServiceAlert',
                                'host, check_name, event_state, event_soft_hard, return_code, payload'),
    'PASSIVE SERVICE CHECK': namedtuple('E_PassiveServiceCheck', 'host, check_name, return_code, payload'),
    'HOST ALERT': namedtuple('E_HostAlert', 'host, event_state, event_soft_hard, return_code, payload'),

    # [1305744274] SERVICE NOTIFICATION: ops;ip-10-114-237-165;Metric ETL;ACKNOWLEDGEMENT (CRITICAL);notify-service-by-email;HTTP CRITICAL: HTTP/1.1 503 Service Unavailable - 394 bytes in 0.010 second response time;datadog;alq # noqa: E501
    'SERVICE NOTIFICATION': namedtuple('E_ServiceNotification',
                                       'contact, host, check_name, event_state, notification_type, payload'),

    # [1296509331] SERVICE FLAPPING ALERT: ip-10-114-97-27;cassandra JVM Heap;STARTED; Service appears to have started flapping (23.4% change >= 20.0% threshold) # noqa: E501
    # [1296662511] SERVICE FLAPPING ALERT: ip-10-114-97-27;cassandra JVM Heap;STOPPED; Service appears to have stopped flapping (3.8% change < 5.0% threshold) # noqa: E501
    'SERVICE FLAPPING ALERT': namedtuple('E_FlappingAlert', 'host, check_name, flap_start_stop, payload'),

    # Reference for external commands: http://old.nagios.org/developerinfo/externalcommands/commandlist.php
    # Command Format:
    # ACKNOWLEDGE_SVC_PROBLEM;<host_name>;<service_description>;<sticky>;<notify>;<persistent>;<author>;<comment>
    # [1305832665] EXTERNAL COMMAND: ACKNOWLEDGE_SVC_PROBLEM;ip-10-202-161-236;Resources ETL;2;1;0;datadog;alq checking
    'ACKNOWLEDGE_SVC_PROBLEM': namedtuple(
        'E_ServiceAck',
        'host, check_name, sticky_ack, notify_ack, persistent_ack, ack_author, payload'
    ),

    # Command Format:
    # ACKNOWLEDGE_HOST_PROBLEM;<host_name>;<sticky>;<notify>;<persistent>;<author>;<comment>
    'ACKNOWLEDGE_HOST_PROBLEM': namedtuple('E_HostAck',
                                           'host, sticky_ack, notify_ack, persistent_ack, ack_author, payload'),

    # Comment Format:
    # PROCESS_SERVICE_CHECK_RESULT;<host_name>;<service_description>;<result_code>;<comment>
    # We ignore it because Nagios will log a "PASSIVE SERVICE CHECK" after
    # receiving this, and we don't want duplicate events to be counted.
    'PROCESS_SERVICE_CHECK_RESULT': False,

    # Host Downtime
    # [1297894825] HOST DOWNTIME ALERT: ip-10-114-89-59;STARTED; Host has entered a period of scheduled downtime
    # [1297894825] SERVICE DOWNTIME ALERT: ip-10-114-237-165;intake;STARTED; Service has entered a period of scheduled downtime # noqa: E501

    'HOST DOWNTIME ALERT': namedtuple('E_HostDowntime', 'host, downtime_start_stop, payload'),
    'SERVICE DOWNTIME ALERT': namedtuple('E_ServiceDowntime', 'host, check_name, downtime_start_stop, payload'),
}

# Regex for the Nagios event log
RE_LINE_REG = re.compile(r'^\[(\d+)\] EXTERNAL COMMAND: (\w+);(.*)$')
RE_LINE_EXT = re.compile(r'^\[(\d+)\] ([^:]+): (.*)$')


class NagiosCheck(AgentCheck):
    SERVICE_CHECK_NAME = INSTANCE_TYPE = "nagios"
    NAGIOS_CONF_KEYS = [
        re.compile(r'^(?P<key>log_file)\s*=\s*(?P<value>.+)$'),
        re.compile(r'^(?P<key>host_perfdata_file_template)\s*=\s*(?P<value>.+)$'),
        re.compile(r'^(?P<key>service_perfdata_file_template)\s*=\s*(?P<value>.+)$'),
        re.compile(r'^(?P<key>host_perfdata_file)\s*=\s*(?P<value>.+)$'),
        re.compile(r'^(?P<key>service_perfdata_file)\s*=\s*(?P<value>.+)$'),
    ]

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.log.setLevel(logging.DEBUG)
        self.account_id = None
        self.nagios_tails = {}
        check_freq = init_config.get("check_freq", 15)
        if instances is not None:
            for instance in instances:
                tailers = []
                nagios_conf = {}
                instance_key = None

                if 'nagios_conf' in instance:  # conf.d check
                    conf_path = instance['nagios_conf']
                    nagios_conf = self.parse_nagios_config(conf_path)
                    instance_key = conf_path
                # Retro compatibility Code
                elif 'nagios_perf_cfg' in instance:
                    conf_path = instance['nagios_perf_cfg']
                    nagios_conf = self.parse_nagios_config(conf_path)
                    instance["collect_host_performance_data"] = True
                    instance["collect_service_performance_data"] = True
                    instance_key = conf_path
                if 'nagios_log' in instance:
                    nagios_conf["log_file"] = instance['nagios_log']
                    if instance_key is None:
                        instance_key = instance['nagios_log']
                # End of retro compatibility code
                if not nagios_conf:
                    self.log.warning("Missing path to nagios_conf")
                    continue

                if 'log_file' in nagios_conf and instance.get('collect_events', True):
                    self.log.debug("Starting to tail the event log")
                    tailers.append(NagiosEventLogTailer(
                        log_path=nagios_conf['log_file'],
                        file_template=None,
                        logger=self.log,
                        hostname=self.hostname,
                        event_func=self.event,
                        gauge_func=self.gauge,
                        freq=check_freq,
                        passive_checks=instance.get('passive_checks_events', False)))
                if 'host_perfdata_file' in nagios_conf and \
                        'host_perfdata_file_template' in nagios_conf and \
                        instance.get('collect_host_performance_data', False):
                    self.log.debug("Starting to tail the host_perfdata file")
                    tailers.append(NagiosHostPerfDataTailer(
                        log_path=nagios_conf['host_perfdata_file'],
                        file_template=nagios_conf['host_perfdata_file_template'],
                        logger=self.log,
                        hostname=self.hostname,
                        event_func=self.event,
                        gauge_func=self.gauge,
                        freq=check_freq))
                if 'service_perfdata_file' in nagios_conf and \
                        'service_perfdata_file_template' in nagios_conf and \
                        instance.get('collect_service_performance_data', False):
                    self.log.debug("Starting to tail the service_perfdata file")
                    tailers.append(NagiosServicePerfDataTailer(
                        log_path=nagios_conf['service_perfdata_file'],
                        file_template=nagios_conf['service_perfdata_file_template'],
                        logger=self.log,
                        hostname=self.hostname,
                        event_func=self.event,
                        gauge_func=self.gauge,
                        freq=check_freq))

                self.nagios_tails[instance_key] = tailers
                self.account_id = self.hostname

    def get_instance_key(self, instance):
        return TopologyInstance(self.INSTANCE_TYPE, self.account_id)

    def check(self, instance):
        """
        Parse until the end of each tailer associated with this instance.
        We match instance and tailers based on the path to the Nagios configuration file

        Special case: Compatibility with the old conf when no conf file is specified
        but the path to the event_log is given
        """
        tags = ["url:{}".format(self.hostname)]
        try:
            instance_key = instance.get('nagios_conf',
                                        instance.get('nagios_perf_cfg',
                                                     instance.get('nagios_log',
                                                                  None)))
            # Bad configuration: This instance does not contain any necessary configuration
            if not instance_key or instance_key not in self.nagios_tails:
                raise Exception('No Nagios configuration file specified')
            for tailer in self.nagios_tails[instance_key]:
                tailer.check()
            i_key = {"type": self.INSTANCE_TYPE, "conf_path": instance.get("nagios_conf"), "url": self.hostname}
            self.get_topology(i_key)

            msg = "Parsed Nagios logs at {}".format(self.hostname)
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=tags, message=msg)
        except Exception as e:
            self.log.exception(str(e))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=tags)

    def get_topology(self, instance_key):
        # Get all hosts
        self.start_snapshot()
        all_hosts = Model.Host.objects.all
        for host in all_hosts:
            if host.host_name is None:
                continue
            id = host.host_name
            self.log.debug("Nagios host object: {}".format(id))
            type = "nagios-host"
            data = {
                "name": host.host_name.strip(),
                "labels": ["nagios-server:" + instance_key.get("url")]
            }
            self.component(id, type, data)
        self.stop_snapshot()

    def parse_nagios_config(self, filename):
        output = {}

        f = None
        try:
            f = open(filename)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                for key in self.NAGIOS_CONF_KEYS:
                    m = key.match(line)
                    if m:
                        output[m.group('key')] = m.group('value')
                        break
            return output
        except Exception as e:
            # Can't parse, assume it's just not working
            # Don't return an incomplete config
            self.log.exception(e)
            raise Exception("Could not parse Nagios config file")
        finally:
            if f is not None:
                f.close()


class NagiosTailer(object):

    def __init__(self, log_path, file_template, logger, hostname, event_func, gauge_func, freq):
        """
        :param log_path: string, path to the file to parse
        :param file_template: string, format of the perfdata file
        :param logger: Logger object
        :param hostname: string, name of the host this agent is running on
        :param event_func: function to create event, should accept dict
        :param gauge_func: function to report a gauge
        :param freq: int, size of bucket to aggregate perfdata metrics
        """
        self.log_path = log_path
        self.log = logger
        self.gen = None
        self.tail = None
        self.hostname = hostname
        self._event = event_func
        self._gauge = gauge_func
        self._line_parsed = 0
        self._freq = freq

        if file_template is not None:
            self.compile_file_template(file_template)

        self.tail = TailFile(self.log, self.log_path, self._parse_line)
        self.gen = self.tail.tail(line_by_line=False, move_end=True)
        next(self.gen)

    def check(self):
        self._line_parsed = 0
        # read until the end of file
        try:
            self.log.debug("Start nagios check for file %s" % (self.log_path))
            next(self.gen)
            self.log.debug("Done nagios check for file %s (parsed %s line(s))" %
                           (self.log_path, self._line_parsed))
        except StopIteration as e:
            self.log.exception(e)
            self.log.warning("Can't tail %s file" % (self.log_path))

    def compile_file_template(self, file_template):
        try:
            # Escape characters that will be interpreted as regex bits
            # e.g. [ and ] in "[SERVICEPERFDATA]"
            regex = re.sub(r'[[\]*]', r'.', file_template)
            regex = re.sub(r'\$([^\$]*)\$', r'(?P<\1>[^\$]*)', regex)
            self.line_pattern = re.compile(regex)
        except Exception as e:
            raise InvalidDataTemplate("%s (%s)" % (file_template, e))

    def _parse_line(self, line):
        raise NotImplementedError


class NagiosEventLogTailer(NagiosTailer):

    def __init__(self, log_path, file_template, logger, hostname, event_func,
                 gauge_func, freq, passive_checks=False):
        """
        :param log_path: string, path to the file to parse
        :param file_template: string, format of the perfdata file
        :param logger: Logger object
        :param hostname: string, name of the host this agent is running on
        :param event_func: function to create event, should accept dict
        :param gauge_func: function to report a gauge
        :param freq: int, size of bucket to aggregate perfdata metrics
        :param passive_checks: bool, enable or not passive checks events
        """
        self.passive_checks = passive_checks
        super(NagiosEventLogTailer, self).__init__(
            log_path, file_template,
            logger, hostname, event_func, gauge_func, freq
        )

    def _parse_line(self, line):
        """Actual nagios parsing
        Return True if we found an event, False otherwise
        """
        # first isolate the timestamp and the event type
        try:
            self._line_parsed = self._line_parsed + 1

            m = RE_LINE_REG.match(line)
            if m is None:
                m = RE_LINE_EXT.match(line)
            if m is None:
                return False
            self.log.debug("Matching line found %s" % line)
            (tstamp, event_type, remainder) = m.groups()
            tstamp = int(tstamp)

            # skip passive checks reports by default for spamminess
            if event_type == 'PASSIVE SERVICE CHECK' and not self.passive_checks:
                return False
            # then retrieve the event format for each specific event type
            fields = EVENT_FIELDS.get(event_type, None)
            if fields is None:
                self.log.warning("Ignoring unknown nagios event for line: %s" % (line[:-1]))
                return False
            elif fields is False:
                # Ignore and skip
                self.log.debug("Ignoring Nagios event for line: %s" % (line[:-1]))
                return False

            # and parse the rest of the line
            parts = list(map(lambda p: p.strip(), remainder.split(';')))
            # Chop parts we don't recognize
            parts = parts[:len(fields._fields)]

            event = self.create_event(tstamp, event_type, self.hostname, fields._make(parts))

            self._event(event)
            self.log.debug("Nagios event: %s" % (event))

            return True
        except Exception:
            self.log.exception("Unable to create a nagios event from line: [%s]" % (line))
            return False

    @staticmethod
    def create_event(timestamp, event_type, hostname, fields):
        """Factory method called by the parsers
        """
        d = fields._asdict()
        d.update({'timestamp': timestamp,
                  'event_type': event_type})

        # if host is localhost, turn that into the internal host name
        host = d.get('host', None)
        if host == "localhost":
            d["host"] = hostname
        return d


class NagiosPerfDataTailer(NagiosTailer):
    perfdata_field = ''  # Should be overriden by subclasses
    metric_prefix = 'nagios'
    pair_pattern = re.compile(r"".join([
        r"'?(?P<label>[^=']+)'?=",
        r"(?P<value>[-0-9.]+)",
        r"(?P<unit>s|us|ms|%|B|KB|MB|GB|TB|c)?",
        r"(;(?P<warn>@?[-0-9.~]*:?[-0-9.~]*))?",
        r"(;(?P<crit>@?[-0-9.~]*:?[-0-9.~]*))?",
        r"(;(?P<min>[-0-9.]*))?",
        r"(;(?P<max>[-0-9.]*))?",
    ]))

    @staticmethod
    def underscorize(s):
        return s.replace(' ', '_').lower()

    def _get_metric_prefix(self, data):
        raise NotImplementedError()

    def _parse_line(self, line):
        matched = self.line_pattern.match(line)
        if matched:
            self.log.debug("Matching line found %s" % line)
            self._line_parsed = self._line_parsed + 1
            data = matched.groupdict()
            metric_prefix = self._get_metric_prefix(data)

            # Parse the prefdata values, which are a space-delimited list of:
            #   'label'=value[UOM];[warn];[crit];[min];[max]
            perf_data = data.get(self.perfdata_field, '').split(' ')
            for pair in perf_data:
                pair_match = self.pair_pattern.match(pair)
                if not pair_match:
                    continue
                else:
                    pair_data = pair_match.groupdict()

                label = pair_data['label']
                timestamp = data.get('TIMET', None)
                if timestamp is not None:
                    timestamp = (int(float(timestamp)) / self._freq) * self._freq
                value = float(pair_data['value'])
                device_name = None

                if '/' in label:
                    # Special case: if the label begins
                    # with a /, treat the label as the device
                    # and use the metric prefix as the metric name
                    metric = '.'.join(metric_prefix)
                    device_name = label

                else:
                    # Otherwise, append the label to the metric prefix
                    # and use that as the metric name
                    metric = '.'.join(metric_prefix + [label])

                host_name = data.get('HOSTNAME', self.hostname)

                optional_keys = ['unit', 'warn', 'crit', 'min', 'max']
                tags = []
                for key in optional_keys:
                    attr_val = pair_data.get(key, None)
                    if attr_val is not None and attr_val != '':
                        tags.append("{0}:{1}".format(key, attr_val))

                self._gauge(metric, value, tags, host_name, device_name)
                self.log.debug("Nagios metric: {}: {}".format(metric, value))


class NagiosHostPerfDataTailer(NagiosPerfDataTailer):
    perfdata_field = 'HOSTPERFDATA'

    def _get_metric_prefix(self, line_data):
        return [self.metric_prefix, 'host']


class NagiosServicePerfDataTailer(NagiosPerfDataTailer):
    perfdata_field = 'SERVICEPERFDATA'

    def _get_metric_prefix(self, line_data):
        metric = [self.metric_prefix]
        middle_name = line_data.get('SERVICEDESC', None)
        if middle_name:
            metric.append(middle_name.replace(' ', '_').lower())
        return metric


class InvalidDataTemplate(Exception):
    pass
