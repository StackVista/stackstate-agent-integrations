from stackstate_checks.base.checks.base import AgentStatefulCheck, TopologyInstance


class TransactionCheck(AgentStatefulCheck):
    def __init__(self, *args, **kwargs):
        instances = [{}]
        super(TransactionCheck, self).__init__("test", {}, instances)

    def stateful_check(self, instance, state):
        return None

    def get_instance_key(self, instance):
        return TopologyInstance(type="testing", url="https://some-url.org/api?page_size=2&token=abc")


class TestTransaction:

    def test_transaction_start_and_stop(self, transaction):
        check = TransactionCheck()
        check._init_transactional_api()
        check.transaction.start_transaction()
        check.transaction.stop_transaction()
        transaction.assert_transaction(check.check_id)

    def test_instance_key_url_sanitization(self):
        check = TransactionCheck()

        assert check._url_as_filename() == "httpssome-urlorgapipage_size2tokenabc"
