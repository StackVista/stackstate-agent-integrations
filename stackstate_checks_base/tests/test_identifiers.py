# -*- coding: utf-8 -*-

# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import unittest

from stackstate_checks.base import Identifiers, to_string


class TestIdentifiers(unittest.TestCase):
    def test_append_lowercase_identifiers(self):
        identifiers = [
            'A9C0C8D2C6112276018F7705562F9CB0',
            'urn:host:/Some Host',
            'urn:dynatrace:/HOST-AA6A5D81A0006807',
            'urn:process:/Some process',
            'urn:container:/ABC',
            'urn:service:/Some Service',
            'urn:service-instance:/Some Service Instance'
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
            'urn:host:/some host',
            'urn:process:/some process',
            'urn:container:/abc',
            'urn:service:/some service',
            'urn:service-instance:/some service instance'
        ]
        self.assertEqual(expected_identifiers, fixed_identifiers)
