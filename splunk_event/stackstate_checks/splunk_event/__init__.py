# (C) StackState 2022
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .__about__ import __version__
from .splunk_event import SplunkEventCheck

__all__ = [
    '__version__',
    'SplunkEventCheck'
]
