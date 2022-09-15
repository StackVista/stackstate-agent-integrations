import pytest

from stackstate_checks.dev import WaitFor
from stackstate_checks.splunk_metric import SplunkMetric


@pytest.mark.integration
def test_metric_search(telemetry, metric_integration_test_instance, test_environment):
    check = SplunkMetric("splunk", {}, {}, [metric_integration_test_instance])

    def run_and_check():
        assert check.run() == ''
        telemetry.assert_total_metrics(10)

    assert WaitFor(run_and_check, attempts=10)() is True
