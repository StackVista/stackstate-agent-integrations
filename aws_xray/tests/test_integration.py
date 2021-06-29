import pytest
from stackstate_checks.aws_xray import AwsCheck
from stackstate_checks.dev import WaitFor


@pytest.mark.integration
class TestXrayCheck:

    def test_xray_check(self, aggregator, xray_instance):
        check = AwsCheck("aws_xray", {}, {}, [xray_instance])

        def run_and_check():
            aggregator.reset()
            assert check.run() == ''
            aggregator.assert_service_check(AwsCheck.SERVICE_CHECK_EXECUTE_NAME, status=AwsCheck.OK, tags=[])

        assert WaitFor(run_and_check, attempts=3)() is True

    def test_xray_check_error_span(self, aggregator, xray_error_instance):
        check = AwsCheck("aws_xray", {}, {}, [xray_error_instance])

        def run_and_check():
            aggregator.reset()
            assert check.run() == ''
            aggregator.assert_service_check(AwsCheck.SERVICE_CHECK_EXECUTE_NAME, status=AwsCheck.OK, tags=[])

        assert WaitFor(run_and_check, attempts=3)() is True
