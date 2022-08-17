import pytest
from stackstate_checks.splunk_event.splunk_event import SplunkEvent
from stackstate_checks.dev import WaitFor


@pytest.mark.integration
def test_event_search(aggregator, splunk_event_instance, test_environment):
    check = SplunkEvent("splunk", {}, {}, [splunk_event_instance])

    def run_and_check():
        assert check.run() == ''
        first_event_data = {
            'event_type': "generic_splunk_event",
            'timestamp': 1488997796.0,
            'msg_title': "generic_splunk_event",
            'source_type_name': 'generic_splunk_event'}
        first_event_tags = [
            "hostname:host01",
            "status:OK",
            "checktag:checktagvalue"]
        aggregator.assert_event(msg_text="Generic splunk event", count=1, tags=first_event_tags, **first_event_data)

    assert WaitFor(run_and_check, attempts=10)() is True
