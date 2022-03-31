from stackstate_checks.base import AgentCheck
from stackstate_checks.base.stubs.datadog_agent import datadog_agent


def test_persistent_cache():
    check = AgentCheck()
    check.check_id = 'test'

    check.write_persistent_cache('foo', 'bar')

    assert datadog_agent.read_persistent_cache('test_foo') == 'bar'
    assert check.read_persistent_cache('foo') == 'bar'
