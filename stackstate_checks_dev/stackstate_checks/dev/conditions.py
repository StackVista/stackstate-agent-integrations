# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import re
import time

from six import string_types
from six.moves.urllib.request import urlopen

from .errors import RetryError
from .structures import LazyFunction
from .subprocess import run_command
from .utils import file_exists


class WaitFor(LazyFunction):
    def __init__(self, func, timeout=1, attempts=60, wait=1, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        self.func = func
        self.timeout = timeout
        self.attempts = attempts
        self.wait = wait
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        last_result = None
        last_error = None
        last_exception = None

        for _ in range(self.attempts):
            try:
                result = self.func(*self.args, **self.kwargs)
            except Exception as e:
                last_error = str(e)
                last_exception = e
                time.sleep(self.wait)
                continue
            else:
                last_result = result

            if last_result is None or last_result is True:
                return True

            time.sleep(self.wait)
        else:
            if last_exception is not None:
                raise RetryError(
                    'Result: {}\n'
                    'Error: {}'.format(
                        repr(last_result),
                        last_error,
                    )
                ) from last_exception
            else:
                raise RetryError(
                    'Result: {}\n'
                    'Error: {}'.format(
                        repr(last_result),
                        last_error,
                    )
                )


class CheckEndpoints(LazyFunction):
    def __init__(self, endpoints, timeout=1, attempts=60, wait=1):
        self.endpoints = [endpoints] if isinstance(endpoints, string_types) else endpoints
        self.timeout = timeout
        self.attempts = attempts
        self.wait = wait

    def __call__(self):
        last_endpoint = ''
        last_error = None

        for _ in range(self.attempts):
            for endpoint in self.endpoints:
                last_endpoint = endpoint
                try:
                    request = urlopen(endpoint, timeout=self.timeout)
                except Exception as e:
                    last_error = str(e)
                    break
                else:
                    status_code = request.getcode()
                    if 400 <= status_code < 600:
                        last_error = 'status {}'.format(status_code)
                        break
            else:
                break

            time.sleep(self.wait)
        else:
            raise RetryError(
                'Endpoint: {}\n'
                'Error: {}'.format(
                    last_endpoint,
                    last_error
                )
            )


class CheckCommandOutput(LazyFunction):
    def __init__(self, command, patterns, matches=1, stdout=True, stderr=True, attempts=60, wait=1):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.attempts = attempts
        self.wait = wait

        if not (self.stdout or self.stderr):
            raise ValueError('Must capture stdout, stderr, or both.')

        if isinstance(patterns, string_types):
            patterns = [patterns]

        self.patterns = [
            re.compile(pattern, re.M) if isinstance(pattern, string_types) else pattern
            for pattern in patterns
        ]

        if matches == 'all':
            self.matches = len(patterns)
        else:
            self.matches = matches

    def __call__(self):
        log_output = ''
        exit_code = 0

        for _ in range(self.attempts):
            result = run_command(self.command, capture=True)
            exit_code = result.code

            if self.stdout and self.stderr:
                log_output = result.stdout + result.stderr
            elif self.stdout:
                log_output = result.stdout
            else:
                log_output = result.stderr

            matches = 0
            for pattern in self.patterns:
                if pattern.search(log_output):
                    matches += 1

            if matches >= self.matches:
                return matches

            time.sleep(self.wait)
        else:
            raise RetryError(
                u'Command: {}\n'
                u'Exit code: {}\n'
                u'Captured Output: {}'.format(
                    self.command,
                    exit_code,
                    log_output
                )
            )


class CheckDockerLogs(CheckCommandOutput):
    def __init__(self, identifier, patterns, matches=1, stdout=True, stderr=True, attempts=60, wait=1):
        if file_exists(identifier):
            command = ['docker-compose', '-f', identifier, 'logs']
        else:
            command = ['docker', 'logs', identifier]

        super(CheckDockerLogs, self).__init__(
            command, patterns, matches=matches, stdout=stdout, stderr=stderr, attempts=attempts, wait=wait
        )
        self.identifier = identifier
