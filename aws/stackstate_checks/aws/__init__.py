# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .__about__ import __version__
from .aws import AwsCheck

__all__ = [
    '__version__',
    'AwsCheck'
]
