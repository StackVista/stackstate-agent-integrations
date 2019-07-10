# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os
import mock

from stackstate_checks.dev.tooling.constants import (
    get_agent_release_requirements, get_agent_requirements, get_root, set_root,
    get_agent_changelog, get_agent_integrations_file
)


def test_get_agent_release_requirements():
    with mock.patch('stackstate_checks.dev.tooling.constants.get_root', return_value='foo'):
        expected = os.path.join('foo', 'requirements-agent-release.txt')
        assert get_agent_release_requirements() == expected


def test_get_agent_requirements():
    with mock.patch('stackstate_checks.dev.tooling.constants.get_root', return_value='foo'):
        expected = os.path.join(
            'foo', 'stackstate_checks_base', 'stackstate_checks', 'base', 'data', 'agent_requirements.in'
        )
        assert get_agent_requirements() == expected


def test_get_agent_integrations_file():
    with mock.patch('stackstate_checks.dev.tooling.constants.get_root', return_value='foo'):
        expected = os.path.join(
            'foo', 'AGENT_INTEGRATIONS.md'
        )
        assert get_agent_integrations_file() == expected


def test_get_agent_changelog():
    with mock.patch('stackstate_checks.dev.tooling.constants.get_root', return_value='foo'):
        expected = os.path.join(
            'foo', 'AGENT_CHANGELOG.md'
        )
        assert get_agent_changelog() == expected


def test_get_root():
    assert get_root() == ''
    set_root('foo')
    assert get_root() == 'foo'
