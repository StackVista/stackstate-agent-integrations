import pytest

from stackstate_checks.base.utils.common import load_json_from_file
from stackstate_checks.splunk_event.splunk_event import SplunkEvent
from stackstate_checks.dev import WaitFor
from .conftest import extract_title_and_type_from_event


@pytest.mark.integration
def test_event_search(aggregator, integration_test_instance, test_environment):
    check = SplunkEvent("splunk", {}, {}, [integration_test_instance])

    def run_and_check():
        assert check.run() == ''
        for event in load_json_from_file("test_events_expected.json", "ci/fixtures"):
            aggregator.assert_event(msg_text=event["msg_text"], count=1, tags=event["tags"],
                                    **extract_title_and_type_from_event(event))

    assert WaitFor(run_and_check, attempts=10)() is True
