# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP

import pytest
import os
import platform
from stackstate_checks.utils.common import pattern_filter, round_value
from stackstate_checks.utils.limiter import Limiter
from stackstate_checks.utils.persistent_state import PersistentState, PersistentInstance, StateNotPersistedException, \
    StateCorruptedException, StateReadException
from six import PY3
from schematics.models import Model
from schematics.types import IntType


class Item:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == other.name


class TestPatternFilter:
    def test_no_items(self):
        items = []
        whitelist = ['mock']

        assert pattern_filter(items, whitelist=whitelist) == []

    def test_no_patterns(self):
        items = ['mock']

        assert pattern_filter(items) is items

    def test_multiple_matches_whitelist(self):
        items = ['abc', 'def', 'abcdef', 'ghi']
        whitelist = ['abc', 'def']

        assert pattern_filter(items, whitelist=whitelist) == ['abc', 'def', 'abcdef']

    def test_multiple_matches_blacklist(self):
        items = ['abc', 'def', 'abcdef', 'ghi']
        blacklist = ['abc', 'def']

        assert pattern_filter(items, blacklist=blacklist) == ['ghi']

    def test_whitelist_blacklist(self):
        items = ['abc', 'def', 'abcdef', 'ghi']
        whitelist = ['def']
        blacklist = ['abc']

        assert pattern_filter(items, whitelist=whitelist, blacklist=blacklist) == ['def']

    def test_key_function(self):
        items = [Item('abc'), Item('def'), Item('abcdef'), Item('ghi')]
        whitelist = ['abc', 'def']

        assert pattern_filter(items, whitelist=whitelist, key=lambda item: item.name) == [
            Item('abc'), Item('def'), Item('abcdef')
        ]


class TestLimiter():
    def test_no_uid(self):
        warnings = []
        limiter = Limiter("my_check", "names", 10, warning_func=warnings.append)
        for i in range(0, 10):
            assert limiter.is_reached() is False
        assert limiter.get_status() == (10, 10, False)

        # Reach limit
        assert limiter.is_reached() is True
        assert limiter.get_status() == (11, 10, True)
        assert warnings == ["Check my_check exceeded limit of 10 names, ignoring next ones"]

        # Make sure warning is only sent once
        assert limiter.is_reached() is True
        assert len(warnings) == 1

    def test_with_uid(self):
        warnings = []
        limiter = Limiter("my_check", "names", 10, warning_func=warnings.append)
        for i in range(0, 20):
            assert limiter.is_reached("dummy1") is False
        assert limiter.get_status() == (1, 10, False)

        for i in range(0, 20):
            assert limiter.is_reached("dummy2") is False
        assert limiter.get_status() == (2, 10, False)
        assert len(warnings) == 0

    def test_mixed(self):
        limiter = Limiter("my_check", "names", 10)

        for i in range(0, 20):
            assert limiter.is_reached("dummy1") is False
        assert limiter.get_status() == (1, 10, False)

        for i in range(0, 5):
            assert limiter.is_reached() is False
        assert limiter.get_status() == (6, 10, False)

    def test_reset(self):
        limiter = Limiter("my_check", "names", 10)

        for i in range(1, 20):
            limiter.is_reached("dummy1")
        assert limiter.get_status() == (1, 10, False)

        limiter.reset()
        assert limiter.get_status() == (0, 10, False)
        assert limiter.is_reached("dummy1") is False
        assert limiter.get_status() == (1, 10, False)


class TestRounding():
    def test_round_half_up(self):
        assert round_value(3.5) == 4.0

    def test_round_modify_method(self):
        assert round_value(3.5, rounding_method=ROUND_HALF_DOWN) == 3.0

    def test_round_modify_sig_digits(self):
        assert round_value(2.555, precision=2) == 2.560
        assert round_value(4.2345, precision=2) == 4.23
        assert round_value(4.2345, precision=3) == 4.235


class TestStorageSchema(Model):
    offset = IntType(required=True, default=0)


class TestPersistentState:

    def test_exception_state_without_valid_location(self, state):
        s = {'a': 'b', 'c': 1, 'd': ['e', 'f', 'g'], 'h': {'i': 'j', 'k': True}}
        instance = PersistentInstance("state.without.location", "")
        with pytest.raises(StateReadException) as e:
            state.persistent_state.get_state(instance)

        if platform.system() == "Windows":
            assert str(e.value) == """[Errno 22] invalid mode ('r') or filename: ''"""
        else:
            assert str(e.value) == """[Errno 2] No such file or directory: ''"""

        with pytest.raises(StateNotPersistedException) as e:
            state.persistent_state.set_state(instance, s)
        if platform.system() == "Windows":
            assert str(e.value) == """[Errno 22] invalid mode ('w') or filename: ''"""
        else:
            assert str(e.value) == """[Errno 2] No such file or directory: ''"""

    def test_exception_corrupted_state(self, state):
        instance = PersistentInstance("state.with.corrupted.data", "state.with.corrupted.data")
        # write "corrupted" data
        with open(instance.file_location, 'w') as f:
            f.write("{'a': 'b', 'c': 1, 'd':....")

        with pytest.raises(StateCorruptedException) as e:
            state.persistent_state.get_state(instance)
        if PY3:
            assert str(e.value) == """Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"""
        else:
            assert str(e.value) == """Expecting property name: line 1 column 2 (char 1)"""

        os.remove(instance.file_location)

    def test_exception_unsupported_data_type_state(self, state):
        instance = PersistentInstance("state.with.unsupported.data", "state.with.unsupported.data")
        with pytest.raises(ValueError) as e:
            state.persistent_state.set_state(instance, 123)
        if PY3:
            assert str(e.value) == "Got unexpected <class 'int'> for argument state, expected dictionary " \
                                   "or schematics.models.Model"
        else:
            assert str(e.value) == "Got unexpected <type 'int'> for argument state, expected dictionary " \
                                   "or schematics.models.Model"

    def test_state_flushing(self, state):
        s = {'a': 'b', 'c': 1, 'd': ['e', 'f', 'g'], 'h': {'i': 'j', 'k': True}}
        instance = PersistentInstance("on.disk.state", "on.disk.state")
        state.assert_state(instance, s)

    def test_state_flushing_with_schema(self, state):
        s = TestStorageSchema({'offset': 10})
        instance = PersistentInstance("on.disk.state.schema", "on.disk.state.schema")
        rs = state.assert_state(instance, s, TestStorageSchema)
        assert rs.offset == s.offset
