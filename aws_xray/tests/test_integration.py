import pytest
from stackstate_checks.aws_xray import AwsCheck
from stackstate_checks.dev import WaitFor


@pytest.mark.integration
@pytest.mark.usefixtures("xray_integration")
def test_xray_check(topology, xray_instance):
    check = AwsCheck("aws_xray", {}, {}, [xray_instance])

    def run_and_check():
        topology.reset()
        assert check.run() == ''
        snapshot = topology.get_snapshot(check.check_id)
        print(snapshot)
        assert len(snapshot['components']) > 1

    assert WaitFor(run_and_check, attempts=10)() is True
