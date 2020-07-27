# (C) StackState, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os

from stackstate_checks.dev import get_docker_hostname, get_here

HERE = get_here()
HOST = get_docker_hostname()

CONTAINER_NAME = "sts-test-nagios"

INSTANCE_INTEGRATION = {
    'nagios_conf': '/etc/nagios/nagios.cfg',
    'collect_host_performance_data': True,
    'collect_service_performance_data': True,
}

CHECK_NAME = 'nagios'
CUSTOM_TAGS = ['optional:tag1']

NAGIOS_TEST_LOG = os.path.join(HERE, 'fixtures', 'nagios')
NAGIOS_TEST_HOST = os.path.join(HERE, 'fixtures', 'host-perfdata')
NAGIOS_TEST_SVC = os.path.join(HERE, 'fixtures', 'service-perfdata')
NAGIOS_TEST_HOST_CFG = os.path.join(HERE, 'fixtures', 'host.cfg')

NAGIOS_TEST_ALT_HOST_TEMPLATE = "[HOSTPERFDATA]\t$TIMET$\t$HOSTNAME$\t$HOSTEXECUTIONTIME$\t$HOSTOUTPUT$\t$HOSTPERFDATA$"
NAGIOS_TEST_ALT_SVC_TEMPLATE = "[SERVICEPERFDATA]\t$TIMET$\t$HOSTNAME$\t$SERVICEDESC$\t$SERVICEEXECUTIONTIME$\t$SERVICELATENCY$\t$SERVICEOUTPUT$\t$SERVICEPERFDATA$" # noqa

NAGIOS_TEST_SVC_TEMPLATE = "DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$" # noqa
NAGIOS_TEST_HOST_TEMPLATE = "DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$" # noqa

DOCKER_NAGIOS_CONF = os.path.join(HERE, 'compose', 'nagios4', 'nagios.cfg')
DOCKER_NAGIOS_LOCALHOST_CONF = os.path.join(HERE, 'compose', 'nagios4', 'localhost.cfg')
