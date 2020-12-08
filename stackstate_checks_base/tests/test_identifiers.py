# -*- coding: utf-8 -*-

# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import unittest

from stackstate_checks.base import Identifiers, to_string


class TestIdentifiers(unittest.TestCase):
    def test_append_lowercase_identifiers(self):
        identifiers = ['a9c0c8d2c6112276018f7705562f9cb0', 'urn:host:/Sales Force Automation',
                       to_string('urn:host:/abcdë.com')]
        fixed_identifiers = Identifiers.append_lowercase_identifiers(identifiers)
        expected_identifiers = ['a9c0c8d2c6112276018f7705562f9cb0', 'urn:host:/Sales Force Automation',
                                to_string('urn:host:/abcdë.com'), 'urn:host:/sales force automation']
        self.assertEqual(expected_identifiers, fixed_identifiers)
