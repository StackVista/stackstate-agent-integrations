# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP

import pytest
import os
from stat import S_IREAD, S_IRGRP, S_IROTH
import platform
from stackstate_checks.utils.common import pattern_filter, round_value
from stackstate_checks.utils.limiter import Limiter
from stackstate_checks.utils.persistent_state import StateManager, StateDescriptor, StateNotPersistedException, \
    StateCorruptedException, StateReadException
from six import PY3
from schematics import Model
from schematics.types import IntType
from schematics.exceptions import DataError


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

        with pytest.raises(DataError) as e:
            StateDescriptor("", "")
        assert str(e.value) == """{"instance_key": ["Value must not be a empty string"]}"""

        instance = StateDescriptor("test", "this")
        # set an invalid file_location for this test
        instance.file_location = ""
        assert state.persistent_state.get_state(instance) is None

        with pytest.raises(StateNotPersistedException) as e:
            state.persistent_state.set_state(instance, s)
        if platform.system() == "Windows":
            assert str(e.value) == """[Error 3] The system cannot find the path specified: ''"""
        else:
            assert str(e.value) == """[Errno 2] No such file or directory: ''"""

    def test_exception_corrupted_state(self, state):
        instance = StateDescriptor("state.with.corrupted.data", ".")
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
        instance = StateDescriptor("state.with.unsupported.data", ".")
        with pytest.raises(ValueError) as e:
            state.persistent_state.set_state(instance, 123)
        if PY3:
            assert str(e.value) == "Got unexpected <class 'int'> for argument state, expected dictionary " \
                                   "or schematics.Model"
        else:
            assert str(e.value) == "Got unexpected <type 'int'> for argument state, expected dictionary " \
                                   "or schematics.Model"

    def test_clear_without_flushing_state(self, state):
        s = {'a': 'b', 'c': 1, 'd': ['e', 'f', 'g'], 'h': {'i': 'j', 'k': True}}
        instance = StateDescriptor("state.with.unsupported.data", ".")
        state.persistent_state.set_state(instance, s, False)
        assert state.persistent_state.clear(instance) is None

    def test_state_flushing(self, state):
        s = {'a': 'b', 'c': 1, 'd': ['e', 'f', 'g'], 'h': {'i': 'j', 'k': True}}
        instance = StateDescriptor("on.disk.state", ".")
        state.assert_state(instance, s)

    def test_state_flushing_read_only(self, state):
        try:
            instance = StateDescriptor("on.disk.state.flush.read.only", ".")
            state.persistent_state.get_state(instance)

            s = {'a': 'b', 'c': 1, 'd': ['e', 'f', 'g'], 'h': {'i': 'j', 'k': True}}
            state.persistent_state.set_state(instance, s)

            # Set the file to read only before writing
            os.chmod(instance.file_location, S_IREAD | S_IRGRP | S_IROTH)

            with pytest.raises(StateNotPersistedException) as e:
                s2 = {'a': 'b'}
                state.persistent_state.set_state(instance, s2)

            assert str(e.value) == """[Errno 13] Permission denied: './on.disk.state.flush.read.only.state'"""

        finally:
            state.persistent_state.clear(instance)

    def test_state_flushing_with_schema(self, state):
        s = TestStorageSchema({'offset': 10})
        instance = StateDescriptor("on.disk.state.schema", ".")
        rs = state.assert_state(instance, s, TestStorageSchema)
        assert rs.offset == s.offset

    def test_state_copy_no_modification_state(self, state):
        s = TestStorageSchema({'offset': 10})
        instance = StateDescriptor("rollback.state.schema", ".")
        s = state.assert_state(instance, s, TestStorageSchema, with_clear=False)

        # update the state in memory
        s.offset = 30

        # assert the state remains unchanged, state should have offset as 10
        state.assert_state(instance, s, TestStorageSchema)
