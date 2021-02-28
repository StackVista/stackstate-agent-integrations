# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

from stackstate_checks.base.errors import CheckException


class BadConfigError(CheckException):
    pass


class ConnectionError(Exception):
    pass
