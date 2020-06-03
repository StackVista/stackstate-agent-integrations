import pytest
from .common import CHECK_NAME
from stackstate_checks.nagios import NagiosCheck


@pytest.mark.usefixtures('sts_environment')
def test_real_topology(sts_agent_check, integration_instance):
    sts_agent_check(integration_instance, rate=True)
