# -*- coding: utf-8 -*-

import unittest
from six import PY3

from stackstate_checks.base import AgentCheck
from stackstate_checks.utils.type_debugging import print_type


class TestEvents(unittest.TestCase):

    def test_fix_encoding(self):
        check = AgentCheck()
        event = {
            'timestamp': 123456789,
            'msg_title': 'new test event',
            'msg_text': u'a few strange characters öüéñ',
            'context': {
                'element_identifiers': [u'urn:test:/value', 123456789],
                "A": {
                    "B": u'bbbbbb',
                    "C": {u"ccc1", "ccc2"},
                    "D": [u'ddddd']
                },
                "E": ["eeeee", u"eeee1"]
            }
        }
        expected_py3 = [
            "key: Fixed, type: <class 'dict'>",
            "key: timestamp, type: <class 'int'>",
            "key: msg_title, type: <class 'str'>",
            "key: msg_text, type: <class 'str'>",
            "key: context, type: <class 'dict'>",
            "key: element_identifiers, type: <class 'list'>",
            "key: element_identifiers, type: <class 'str'>",
            "key: element_identifiers, type: <class 'int'>",
            "key: context, type: <class 'dict'>",
            "key: A, type: <class 'dict'>",
            "key: C, type: <class 'set'>",
            "key: C, type: <class 'str'>",
            "key: C, type: <class 'str'>",
            "key: B, type: <class 'str'>",
            "key: D, type: <class 'list'>",
            "key: D, type: <class 'str'>",
            "key: E, type: <class 'list'>",
            "key: E, type: <class 'str'>",
            "key: E, type: <class 'str'>",
        ]

        expected_py2 = [x.replace("<class", "<type") for x in expected_py3]

        expected_types = expected_py3 if PY3 else expected_py2
        fixed_event = check._fix_encoding(event)
        fixed_types = print_type('Fixed', fixed_event)
        for expected in expected_types:
            assert expected in fixed_types

    def test_removal_of_empty_elements(self):
        check = AgentCheck()
        event = {
            'A': {
                'AA': u'AA123',
                'AB': ''
            },
            'B': ['b1', '', 'b3']
        }
        fixed_event = check._fix_encoding(event)
        self.assertIn('AA', fixed_event['A'].keys())
        self.assertNotIn('AB', fixed_event['A'].keys())
        self.assertEqual(2, len(fixed_event['B']))
