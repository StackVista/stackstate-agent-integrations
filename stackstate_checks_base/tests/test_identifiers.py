# -*- coding: utf-8 -*-

# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import unittest

from stackstate_checks.base import Identifiers, to_string
from six import PY3


if PY3:
    long = int


class TestIdentifiers(unittest.TestCase):
    def test_create_host_identifier(self):
        self.assertEqual(Identifiers.create_host_identifier('hostname'), 'urn:host:/hostname')
        self.assertEqual(Identifiers.create_host_identifier('ABCDë.com'), 'urn:host:/ABCDë.com')
        self.assertEqual(Identifiers.create_host_identifier(''), 'urn:host:/')

    def test_create_process_identifier(self):
        self.assertEqual(Identifiers.create_process_identifier('hostname', 1, 123), 'urn:process:/hostname:1:123')
        self.assertEqual(Identifiers.create_process_identifier('ABCDë.com', 1, '123'), 'urn:process:/ABCDë.com:1:123')
        self.assertEqual(Identifiers.create_process_identifier('ABCDë.com', 1, long(123)),
                         'urn:process:/ABCDë.com:1:123')
        self.assertEqual(Identifiers.create_process_identifier('', 1, float(123)), 'urn:process:/:1:123.0')

    def test_create_container_identifier(self):
        self.assertEqual(Identifiers.create_container_identifier('hostname', 123), 'urn:container:/hostname:123')
        self.assertEqual(Identifiers.create_container_identifier('ABCDë.com', '123'), 'urn:container:/ABCDë.com:123')
        self.assertEqual(Identifiers.create_container_identifier('', long(123)), 'urn:container:/:123')

    def test_create_trace_service_identifier(self):
        self.assertEqual(Identifiers.create_trace_service_identifier('service-name'), 'urn:service:/service-name')
        self.assertEqual(Identifiers.create_trace_service_identifier('ABCDë.com'), 'urn:service:/ABCDë.com')
        self.assertEqual(Identifiers.create_trace_service_identifier(''), 'urn:service:/')

    def test_create_trace_service_instance_identifier(self):
        self.assertEqual(Identifiers.create_trace_service_instance_identifier('service-name'),
                         'urn:service-instance:/service-name')
        self.assertEqual(Identifiers.create_trace_service_instance_identifier('ABCDë.com'),
                         'urn:service-instance:/ABCDë.com')
        self.assertEqual(Identifiers.create_trace_service_instance_identifier(''), 'urn:service-instance:/')

    def test_create_integration_identifier(self):
        self.assertEqual(Identifiers.create_integration_identifier('hostname', 'integration-name'),
                         'urn:agent-integration:/hostname:integration-name')
        self.assertEqual(Identifiers.create_integration_identifier('hostname', 'ABCDë.com'),
                         'urn:agent-integration:/hostname:ABCDë.com')
        self.assertEqual(Identifiers.create_integration_identifier('hostname', ''),
                         'urn:agent-integration:/hostname:')

    def test_create_integration_instance_identifier(self):
        self.assertEqual(Identifiers.create_integration_instance_identifier('hostname', 'integration-name',
                                                                            'integration-type'),
                         'urn:agent-integration-instance:/hostname:integration-name:integration-type')
        self.assertEqual(Identifiers.create_integration_instance_identifier('hostname', 'ABCDë.com',
                                                                            'integration-type'),
                         'urn:agent-integration-instance:/hostname:ABCDë.com:integration-type')
        self.assertEqual(Identifiers.create_integration_instance_identifier('hostname', '',
                                                                            'integration-type'),
                         'urn:agent-integration-instance:/hostname::integration-type')

    def test_create_agent_identifier(self):
        self.assertEqual(Identifiers.create_agent_identifier('hostname'), 'urn:stackstate-agent:/hostname')
        self.assertEqual(Identifiers.create_agent_identifier('ABCDë.com'), 'urn:stackstate-agent:/ABCDë.com')
        self.assertEqual(Identifiers.create_agent_identifier(''), 'urn:stackstate-agent:/')

    def test_create_custom_identifier(self):
        self.assertEqual(Identifiers.create_custom_identifier('namespace', 'hostname'),
                         'urn:namespace:/hostname')
        self.assertEqual(Identifiers.create_custom_identifier('namespace', 'ABCDë.com'),
                         'urn:namespace:/ABCDë.com')
        self.assertEqual(Identifiers.create_custom_identifier('namespace', ''),
                         'urn:namespace:/')

    def test_append_lowercase_identifiers(self):
        identifiers = [
            'A9C0C8D2C6112276018F7705562F9CB0',
            'urn:host:/Some Host',
            'urn:dynatrace:/HOST-AA6A5D81A0006807',
            'urn:process:/Some process',
            'urn:container:/ABC',
            'urn:service:/Some Service',
            'urn:service-instance:/Some Service Instance',
            'urn:host:/ABCDë.com'
        ]
        fixed_identifiers = Identifiers.append_lowercase_identifiers(identifiers)
        expected_identifiers = [
            'A9C0C8D2C6112276018F7705562F9CB0',
            'urn:host:/Some Host',
            'urn:dynatrace:/HOST-AA6A5D81A0006807',
            'urn:process:/Some process',
            'urn:container:/ABC',
            'urn:service:/Some Service',
            'urn:service-instance:/Some Service Instance',
            'urn:host:/ABCDë.com',
            'urn:host:/some host',
            'urn:process:/some process',
            'urn:container:/abc',
            'urn:service:/some service',
            'urn:service-instance:/some service instance',
            'urn:host:/abcdë.com'
        ]
        self.assertEqual(expected_identifiers, fixed_identifiers)
