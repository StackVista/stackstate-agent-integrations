import pytest


@pytest.mark.e2e
def test_e2e(sts_agent_check, instance):
    # This integration is based on tailing logs but because there is an agent running
    # in the agent image we cannot guarantee that we will pick specific metrics on a test.
    # The test will fail if the integration cannot read nagios config or related files
    sts_agent_check(instance, rate=True)
