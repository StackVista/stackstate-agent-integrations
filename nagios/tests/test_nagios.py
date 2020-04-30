# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import tempfile

import mock
from pynag.Utils import misc

from stackstate_checks.base import ensure_bytes
from stackstate_checks.base.stubs import topology
from stackstate_checks.nagios import NagiosCheck

from .common import (
    CHECK_NAME,
    NAGIOS_TEST_LOG, NAGIOS_TEST_HOST_CFG
)


def test_line_parser(aggregator):
    """
    Parse lines
    """

    # Get the config
    config, nagios_cfg = get_config(
        '\n'.join(["log_file={0}".format(NAGIOS_TEST_LOG)]),
        events=True
    )

    # Set up the check
    nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])

    nagios.get_topology = mocked_topology

    # Run the check once
    nagios.check(config['instances'][0])

    nagios_tailer = nagios.nagios_tails[nagios_cfg.name][0]
    counters = {}

    for line in open(NAGIOS_TEST_LOG).readlines():
        parsed = nagios_tailer._parse_line(line)
        if parsed:
            event = aggregator.events[-1]
            t = event["event_type"]
            assert t in line
            assert int(event["timestamp"]) > 0, line
            assert event["host"] is not None, line
            counters[t] = counters.get(t, 0) + 1

            if t == "SERVICE ALERT":
                assert event["event_soft_hard"] in ("SOFT", "HARD"), line
                assert event["event_state"] in ("CRITICAL", "WARNING", "UNKNOWN", "OK"), line
                assert event["check_name"] is not None
            elif t == "SERVICE NOTIFICATION":
                assert event["event_state"] in (
                    "ACKNOWLEDGEMENT", "OK", "CRITICAL", "WARNING", "ACKNOWLEDGEMENT (CRITICAL)"), line
            elif t == "SERVICE FLAPPING ALERT":
                assert event["flap_start_stop"] in ("STARTED", "STOPPED"), line
                assert event["check_name"] is not None
            elif t == "ACKNOWLEDGE_SVC_PROBLEM":
                assert event["check_name"] is not None
                assert event["ack_author"] is not None
                assert int(event["sticky_ack"]) >= 0
                assert int(event["notify_ack"]) >= 0
            elif t == "ACKNOWLEDGE_HOST_PROBLEM":
                assert event["ack_author"] is not None
                assert int(event["sticky_ack"]) >= 0
                assert int(event["notify_ack"]) >= 0
            elif t == "HOST DOWNTIME ALERT":
                assert event["host"] is not None
                assert event["downtime_start_stop"] in ("STARTED", "STOPPED")

    assert counters["SERVICE ALERT"] == 301
    assert counters["SERVICE NOTIFICATION"] == 120
    assert counters["HOST ALERT"] == 3
    assert counters["SERVICE FLAPPING ALERT"] == 7
    assert counters["CURRENT HOST STATE"] == 8
    assert counters["CURRENT SERVICE STATE"] == 52
    assert counters["SERVICE DOWNTIME ALERT"] == 3
    assert counters["HOST DOWNTIME ALERT"] == 5
    assert counters["ACKNOWLEDGE_SVC_PROBLEM"] == 4
    assert "ACKNOWLEDGE_HOST_PROBLEM" not in counters


def test_continuous_bulk_parsing(aggregator):
    """
    Make sure the Tailer continues to parse Nagios as the file grows
    """
    test_data = open(NAGIOS_TEST_LOG).read()
    events = []
    ITERATIONS = 10
    log_file = tempfile.NamedTemporaryFile(mode="a+b")
    log_file.write(test_data.encode('utf-8'))
    log_file.flush()

    # Get the config
    config, nagios_cfg = get_config('\n'.join(["log_file={0}".format(log_file.name)]), events=True)

    # Set up the check
    nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])
    nagios.get_topology = mocked_topology

    for i in range(ITERATIONS):
        log_file.write(test_data.encode('utf-8'))
        log_file.flush()
        nagios.check(config['instances'][0])
        events.extend(events)

    log_file.close()
    assert len(aggregator.events) == ITERATIONS * 503


def test_get_topology(dummy_instance):
    """
    Collect Nagios Host components as topology
    """
    instance_key = {"type": "nagios", "url": "192.1.1.1", "conf_path": dummy_instance.get("nagios_conf")}

    # Mock parse_nagios_config
    NagiosCheck.parse_nagios_config = mock.MagicMock()
    NagiosCheck.parse_nagios_config.return_value = {"key": "value"}

    # Set up the check
    nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=[dummy_instance])

    # Creates a fake nagios environment with minimal configs in /tmp/
    environment = misc.FakeNagiosEnvironment()
    # Create temporary director with minimal config and one by default host 'ok_host'
    environment.create_minimal_environment()
    # Update the global variables in pynag.Model
    environment.update_model()

    environment.import_config(NAGIOS_TEST_HOST_CFG)
    environment.config.parse_maincfg()

    nagios.get_topology(instance_key)
    snaphot = topology.get_snapshot(nagios.check_id)

    # topology should return 3 components, 2 from cfg and 1 default
    assert len(snaphot.get('components')) == 3

    # topology should return 1st host name as components from host.cfg
    assert snaphot.get('components')[0].get('id') == 'prod-api-1'


def get_config(nagios_conf, events=False, service_perf=False, host_perf=False):
    """
    Helper to generate a valid Nagios configuration
    """
    nagios_conf = ensure_bytes(nagios_conf)

    nagios_cfg = tempfile.NamedTemporaryFile(mode="a+b")
    nagios_cfg.write(nagios_conf)
    nagios_cfg.flush()

    config = {
        'instances': [
            {
                'nagios_conf': nagios_cfg.name,
                'collect_events': events,
                'collect_service_performance_data': service_perf,
                'collect_host_performance_data': host_perf
            }
        ]
    }

    return config, nagios_cfg


def mocked_topology(*args, **kwargs):
    return {'instance': {'key': 'dummy'}, 'components': []}
