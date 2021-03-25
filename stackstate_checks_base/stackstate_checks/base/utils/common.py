# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import inspect
import json
from decimal import ROUND_HALF_UP, Decimal
import os
import re

from six import PY3, text_type
from six.moves.urllib.parse import urlparse


def ensure_string(s):
    if isinstance(s, text_type):
        s = s.encode('utf-8')
    return s


def ensure_unicode(s):
    if isinstance(s, bytes):
        s = s.decode('utf-8')
    return s


to_string = ensure_unicode if PY3 else ensure_string


def round_value(value, precision=0, rounding_method=ROUND_HALF_UP):
    precision = '0.{}'.format('0' * precision)
    return float(Decimal(str(value)).quantize(Decimal(precision), rounding=rounding_method))


def get_docker_hostname():
    return urlparse(os.getenv('DOCKER_HOST', '')).hostname or 'localhost'


def pattern_filter(items, whitelist=None, blacklist=None, key=None):
    """This filters `items` by a regular expression `whitelist` and/or
    `blacklist`, with the `blacklist` taking precedence. An optional `key`
    function can be provided that will be passed each item.
    """
    key = key or __return_self
    if whitelist:
        whitelisted = _filter(items, whitelist, key)

        if blacklist:
            blacklisted = _filter(items, blacklist, key)
            # Remove any blacklisted items from the whitelisted ones.
            whitelisted.difference_update(blacklisted)

        return [item for item in items if key(item) in whitelisted]

    elif blacklist:
        blacklisted = _filter(items, blacklist, key)
        return [item for item in items if key(item) not in blacklisted]

    else:
        return items


def _filter(items, pattern_list, key):
    return {
        key(item) for pattern in pattern_list
        for item in items
        if re.search(pattern, key(item))
    }


def __return_self(obj):
    return obj


def read_file(filename, extended_path=None):
    """
    Return file contents as string. It supports UTF-8 characters in both PY2 and PY3.
    :param filename: String
    :param extended_path: Optional path
    :return: String with file contents.
    """
    with open(_get_path_to_file(filename, extended_path), "r") as f:
        return f.read() if PY3 else f.read().decode("utf-8")


def load_json_from_file(filename, extended_path=None):
    """
    Returns dictionary with file contents. It supports UTF-8 characters in both PY2 and PY3.
    :param filename: String
    :param extended_path: Optional path
    :return: Dictionary with the file contents.
    """
    raw_json_file = read_file(filename, extended_path)
    return json.loads(raw_json_file)


def _get_path_to_file(filename, extended_path=None):
    """
    Only works when called from load_json_from_file or read_file functions.
    It calculates absolute path to filename relative to caller file location.
    Caller file is python module where read_file or load_json_from_file was called.
    :param filename: String
    :param extended_path: Optional path
    :return: String with absolut path to file
    """
    caller_file = inspect.stack()[2].filename if PY3 else inspect.stack()[2][1]
    if caller_file == __file__:
        caller_file = inspect.stack()[3].filename if PY3 else inspect.stack()[3][1]
    print("caller_file", caller_file)
    path_to_callers_file = os.path.abspath(caller_file)
    path_with_extended_part = os.path.join(os.path.dirname(path_to_callers_file), extended_path)
    path_to_file = os.path.join(path_with_extended_part, filename)
    return path_to_file
