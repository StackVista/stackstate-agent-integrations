# (C) Datadog, Inc. 2010-2018
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from stackstate_checks.dev import get_docker_hostname

HOST = get_docker_hostname()
PORT = '8089'
USER = 'admin'
PASSWORD = 'admin12345'
