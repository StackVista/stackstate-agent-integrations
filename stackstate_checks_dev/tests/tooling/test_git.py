# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import mock

from stackstate_checks.dev.tooling.constants import set_root
from stackstate_checks.dev.tooling.git import (
    get_current_branch, files_changed, get_commits_since, git_show_file,
    git_commit, git_tag, git_tag_list
)


def test_get_current_branch():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            get_current_branch()
            chdir.assert_called_once_with('/foo/')
            run.assert_called_once_with('git rev-parse --abbrev-ref HEAD', capture='out')


def test_files_changed():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            run.return_value = mock.MagicMock()
            expected = ['foo', 'bar', 'baz']
            run.return_value.stdout = "\n".join(expected)
            set_root('/foo/')
            retval = files_changed()
            chdir.assert_called_once_with('/foo/')
            run.assert_called_once_with('git diff --name-only master...', capture='out')
            assert retval == expected


def test_get_commits_since():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            get_commits_since('my-check')
            chdir.assert_called_once_with('/foo/')
            get_commits_since('my-check', target_tag='the-tag')
            run.assert_any_call('git log --pretty=%s /foo/my-check', capture=True)
            run.assert_any_call('git log --pretty=%s the-tag... /foo/my-check', capture=True)


def test_git_show_file():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            git_show_file('path-string', 'git-ref-string')
            chdir.assert_called_once_with('/foo/')
            run.assert_called_once_with('git show git-ref-string:path-string', capture=True)


def test_git_commit():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            targets = ['a', 'b', 'c']

            # all good
            run.return_value = mock.MagicMock(code=0)
            git_commit(targets, 'my message')
            chdir.assert_called_once_with('/foo/')
            run.assert_any_call('git add /foo/a /foo/b /foo/c')
            run.assert_any_call('git commit -m "my message"')
            chdir.reset_mock()
            run.reset_mock()

            # all good, more params
            git_commit(targets, 'my message', force=True, sign=True)
            chdir.assert_called_once_with('/foo/')
            run.assert_any_call('git add -f /foo/a /foo/b /foo/c')
            run.assert_any_call('git commit -S -m "my message"')
            chdir.reset_mock()
            run.reset_mock()

            # git add fails
            run.return_value = mock.MagicMock(code=123)
            git_commit(targets, 'my message')
            chdir.assert_called_once_with('/foo/')
            # we expect only one call, git commit should not be called
            run.assert_called_once_with('git add /foo/a /foo/b /foo/c')


def test_git_tag():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            run.return_value = mock.MagicMock(code=0)

            # all good
            git_tag('tagname')
            chdir.assert_called_once_with('/foo/')
            run.assert_called_once_with('git tag -a tagname -m "tagname"', capture=True)
            assert run.call_count == 1
            chdir.reset_mock()
            run.reset_mock()

            # again with push
            git_tag('tagname', push=True)
            chdir.assert_called_once_with('/foo/')
            run.assert_any_call('git tag -a tagname -m "tagname"', capture=True)
            run.assert_any_call('git push origin tagname')
            chdir.reset_mock()
            run.reset_mock()

            # again with tag failing
            run.return_value = mock.MagicMock(code=123)
            git_tag('tagname', push=True)
            chdir.assert_called_once_with('/foo/')
            # we expect only one call, git push should be skipped
            run.assert_called_once_with('git tag -a tagname -m "tagname"', capture=True)


def test_git_tag_list():
    with mock.patch('stackstate_checks.dev.tooling.git.chdir') as chdir:
        with mock.patch('stackstate_checks.dev.tooling.git.run_command') as run:
            set_root('/foo/')
            expected = ['a', 'b', 'c']
            run.return_value = mock.MagicMock(code=0)
            run.return_value.stdout = '\n'.join(expected)

            # no pattern
            res = git_tag_list()
            assert res == expected
            chdir.assert_called_once_with('/foo/')
            chdir.reset_mock()
            run.reset_mock()

            # pattern
            res = git_tag_list(r'^a')
            assert res == ['a']
            chdir.assert_called_once_with('/foo/')
