# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from .__about__ import __version__
from .prometheus_health import PrometheusHealthCheck

__all__ = [
    '__version__',
    'PrometheusHealthCheck'
]
