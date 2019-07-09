# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import mock
import pytest

from stackstate_checks.dev.errors import ManifestError
from stackstate_checks.dev.tooling.release import (
    get_package_name, get_folder_name, get_agent_requirement_line
)


def test_get_package_name():
    assert get_package_name('stackstate_checks_base') == 'stackstate-checks-base'
    assert get_package_name('my_check') == 'stackstate-my-check'


def test_get_folder_name():
    assert get_folder_name('stackstate-checks-base') == 'stackstate_checks_base'
    assert get_folder_name('stackstate-my-check') == 'my_check'


def test_get_agent_requirement_line():
    res = get_agent_requirement_line('stackstate_checks_base', '1.1.0')
    assert res == 'stackstate-checks-base==1.1.0'

    with mock.patch('stackstate_checks.dev.tooling.release.load_manifest') as load:
        # wrong manifest
        load.return_value = {}
        with pytest.raises(ManifestError):
            get_agent_requirement_line('foo', '1.2.3')

        # all platforms
        load.return_value = {
            "supported_os": [
                "linux",
                "mac_os",
                "windows"
            ]
        }
        res = get_agent_requirement_line('foo', '1.2.3')
        assert res == 'stackstate-foo==1.2.3'

        # one platform
        load.return_value = {
            "supported_os": [
                "linux"
            ]
        }
        res = get_agent_requirement_line('foo', '1.2.3')
        assert res == "stackstate-foo==1.2.3; sys_platform == 'linux2'"

        # multiple platforms
        load.return_value = {
            "supported_os": [
                "linux",
                "mac_os",
            ]
        }
        res = get_agent_requirement_line('foo', '1.2.3')
        assert res == "stackstate-foo==1.2.3; sys_platform != 'win32'"
