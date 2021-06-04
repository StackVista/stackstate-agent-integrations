"""
    StackState.
    Splunk topology extraction
"""

# 3rd party
import sys
import time

from stackstate_checks.base import AgentCheck, TopologyInstance
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client import FinalizeException, TokenExpiredException, SplunkClient

from stackstate_checks.splunk.config.splunk_instance_config import SplunkSavedSearch, SplunkInstanceConfig, \
    SavedSearches, chunks, take_optional_field


class SavedSearch(SplunkSavedSearch):
    def __init__(self, element_type, instance_config, saved_search_instance):
        super(SavedSearch, self).__init__(instance_config, saved_search_instance)
        self.element_type = element_type


class InstanceConfig(SplunkInstanceConfig):
    def __init__(self, instance, init_config):
        super(InstanceConfig, self).__init__(instance, init_config, {
            'default_request_timeout_seconds': 5,
            'default_search_max_retry_count': 3,
            'default_search_seconds_between_retries': 1,
            'default_verify_ssl_certificate': False,
            'default_batch_size': 1000,
            'default_saved_searches_parallel': 3,
            'default_app': "search",
            'default_parameters': {
                "force_dispatch": True,
                "dispatch.now": True
            }
        })

        if 'default_polling_interval_seconds' in init_config:
            raise CheckException(
                "deprecated config `init_config.default_polling_interval_seconds` found."
                " Please use the new init_config.min_collection_interval.")


class Instance:
    INSTANCE_TYPE = "splunk"

    def __init__(self, instance, init_config):
        self.instance_config = InstanceConfig(instance, init_config)
        self.splunkClient = SplunkClient(self.instance_config)

        self.snapshot = bool(instance.get('snapshot', True))

        # no saved searches may be configured
        if not isinstance(instance['component_saved_searches'], list):
            instance['component_saved_searches'] = []
        if not isinstance(instance['relation_saved_searches'], list):
            instance['relation_saved_searches'] = []

        # transform component and relation saved searches to SavedSearch objects
        components = [SavedSearch("component", self.instance_config, saved_search_instance)
                      for saved_search_instance in instance['component_saved_searches']]
        relations = [SavedSearch("relation", self.instance_config, saved_search_instance)
                     for saved_search_instance in instance['relation_saved_searches']]

        self.saved_searches = SavedSearches(components + relations)
        self.tags = instance.get('tags', [])
        self.splunk_ignore_saved_search_errors = instance.get('ignore_saved_search_errors', False)

        if 'polling_interval_seconds' in instance:
            raise CheckException(
                "deprecated config `polling_interval_seconds` found. Please use the new min_collection_interval.")

        self.saved_searches_parallel = int(
            instance.get('saved_searches_parallel', self.instance_config.default_saved_searches_parallel))


class SplunkTopology(AgentCheck):
    SERVICE_CHECK_NAME = "splunk.topology_information"
    EXCLUDE_FIELDS = set(['_raw', '_indextime', '_cd', '_serial', '_sourcetype', '_bkt', '_si'])

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(SplunkTopology, self).__init__(name, init_config, agentConfig, instances)
        # Data to keep over check runs, keyed by instance url
        self.instance_data = dict()

    def get_instance_key(self, instance):
        return TopologyInstance(Instance.INSTANCE_TYPE, instance["url"])

    def check(self, instance):
        authentication = None
        if 'url' not in instance:
            raise CheckException('Splunk topology instance missing "url" value.')
        if 'username' in instance and 'password' in instance and 'authentication' not in instance:
            self.log.warning("This username and password configuration will be deprecated soon. Please use the new "
                             "updated configuration from the conf")
        if 'authentication' in instance:
            authentication = instance["authentication"]
            if 'basic_auth' not in authentication and 'token_auth' not in authentication:
                raise CheckException('Splunk topology instance missing "authentication.basic_auth" or '
                                     '"authentication.token_auth" value')
            if 'basic_auth' in authentication:
                basic_auth = authentication["basic_auth"]
                if 'username' not in basic_auth:
                    raise CheckException('Splunk topology instance missing "authentication.basic_auth.username" value')
                if 'password' not in basic_auth:
                    raise CheckException('Splunk topology instance missing "authentication.basic_auth.password" value')
            if 'token_auth' in authentication:
                token_auth = authentication["token_auth"]
                if 'name' not in token_auth:
                    raise CheckException('Splunk topology instance missing "authentication.token_auth.name" value')
                if 'initial_token' not in token_auth:
                    raise CheckException('Splunk topology instance missing "authentication.token_auth.initial_token" '
                                         'value')
                if 'audience' not in token_auth:
                    raise CheckException('Splunk topology instance missing "authentication.token_auth.audience" value')

        if instance["url"] not in self.instance_data:
            self.instance_data[instance["url"]] = Instance(instance, self.init_config)

        state = self.load_state(instance)

        instance = self.instance_data[instance["url"]]

        if instance.snapshot:
            self.start_snapshot()

        try:
            if authentication and 'token_auth' in authentication:
                self.log.debug("Using token based authentication mechanism")
                base_url = instance.instance_config.base_url
                self._token_auth_session(instance, authentication, base_url, state)
            else:
                self.log.debug("Using basic authentication mechanism")
                self._auth_session(instance)

            saved_searches = self._saved_searches(instance)
            instance.saved_searches.update_searches(self.log, saved_searches)
            all_success = True

            for saved_searches in chunks(instance.saved_searches.searches, instance.saved_searches_parallel):
                all_success &= self._dispatch_and_await_search(instance, state, saved_searches)

            # If everything was successful, update the timestamp
            if all_success:
                self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)

            if instance.snapshot:
                self.stop_snapshot()
        except TokenExpiredException as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.tags, message=str(e.message))
            self.log.exception("Splunk topology exception: %s" % str(e))
        except Exception as e:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, tags=instance.tags, message=str(e))
            self.log.exception("Splunk topology exception: %s" % str(e))
            if not instance.splunk_ignore_saved_search_errors:
                raise CheckException("Splunk topology failed with message: %s" % e, None, sys.exc_info()[2])

    def _dispatch_and_await_search(self, instance, state, saved_searches):
        start_time = time.time()

        # don't dispatch if sids present
        for saved_search in saved_searches:
            try:
                persist_status_key = instance.instance_config.base_url + saved_search.name
                if state.get(persist_status_key) is not None:
                    sid = state[persist_status_key]
                    self._finalize_sid(instance, sid, saved_search)
                    self.update_persistent_state(state, instance.instance_config.base_url, saved_search.name, sid,
                                                 'remove')
            except FinalizeException as e:
                self.log.exception(
                    "Got an error %s while finalizing the saved search %s" % (e.message, saved_search.name))
                if not instance.splunk_ignore_saved_search_errors:
                    raise e
                self.log.warning("Ignoring finalize exception as ignore_saved_search_errors flag is true.")

        search_ids = [(self._dispatch_saved_search(instance, state, saved_search), saved_search)
                      for saved_search in saved_searches]

        all_success = True

        for (sid, saved_search) in search_ids:
            self.log.debug("Processing saved search: %s." % saved_search.name)
            if sid is None:
                self.log.warn("Skipping the saved search %s as it doesn't exist " % saved_search.name)
                continue
            all_success &= self._process_saved_search(sid, saved_search, instance, start_time)

        return all_success

    def _process_saved_search(self, search_id, saved_search, instance, start_time):
        count = 0
        fail_count = 0

        try:
            responses = self._search(search_id, saved_search, instance)

            for response in responses:
                for message in response['messages']:
                    if message['type'] != "FATAL" and message['type'] != "INFO":
                        self.log.info(
                            "Received unhandled message for saved search %s, got: %s" % (saved_search.name, message))

                count += len(response["results"])
                # process components and relations
                if saved_search.element_type == "component":
                    fail_count += self._extract_components(instance, response)
                elif saved_search.element_type == "relation":
                    fail_count += self._extract_relations(instance, response)

            self.log.debug(
                "Saved search done: %s in time %d with results %d of which %d failed" % (
                    saved_search.name, time.time() - start_time, count, fail_count)
            )

            if fail_count != 0:
                if (fail_count != count) and (count != 0):
                    msg = "The saved search '%s' contained %d incomplete %s records" % (
                                saved_search.name, fail_count, saved_search.element_type)
                    self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance.tags, message=msg)
                    self.log.warn(msg)
                    return False
                elif count != 0:
                    raise CheckException(
                        "All result of saved search '%s' contained incomplete data" % saved_search.name)

        except CheckException as e:
            if not instance.splunk_ignore_saved_search_errors:
                self.log.error("Received Check exception while processing saved search " + saved_search.name)
                raise e
            self.log.warning(
                "Check exception occured %s while processing saved search name %s" % (str(e), saved_search.name))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance.tags, message=str(e))
            return False
        except Exception as e:
            if not instance.splunk_ignore_saved_search_errors:
                self.log.error("Received an exception while processing saved search " + saved_search.name)
                raise e
            self.log.warning("Got an error %s while processing saved search name %s" % (str(e), saved_search.name))
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.WARNING, tags=instance.tags, message=str(e))
            return False

        return True

    def _saved_searches(self, instance):
        return instance.splunkClient.saved_searches()

    def _search(self, search_id, saved_search, instance):
        return instance.splunkClient.saved_search_results(search_id, saved_search)

    def _status(self):
        """ This method is mocked for testing. """
        return self.status

    def _dispatch_saved_search(self, instance, state, saved_search):
        """
        Initiate a saved search, returning the search id
        :param instance: Instance of the splunk instance
        :param saved_search: SavedSearch to dispatch
        :return: search id
        """
        parameters = saved_search.parameters
        # json output_mode is mandatory for response parsing
        parameters["output_mode"] = "json"

        splunk_user = instance.instance_config.username
        splunk_app = saved_search.app
        splunk_ignore_saved_search_errors = instance.splunk_ignore_saved_search_errors

        self.log.debug("Dispatching saved search: %s." % saved_search.name)
        sid = self._dispatch(instance, saved_search, splunk_user, splunk_app, splunk_ignore_saved_search_errors,
                             parameters)
        self.update_persistent_state(state, instance.instance_config.base_url, saved_search.name, sid, 'add')
        return sid

    def _extract_components(self, instance, result):
        fail_count = 0

        for data in result["results"]:
            # Required fields
            external_id = take_optional_field("id", data)
            comp_type = take_optional_field("type", data)

            # Add tags to data
            if 'tags' in data and instance.tags:
                data['tags'] += instance.tags
            elif instance.tags:
                data['tags'] = instance.tags

            # We don't want to present all fields
            filtered_data = self._filter_fields(data)

            if external_id is not None and comp_type is not None:
                self.component(external_id, comp_type, filtered_data)
            else:
                fail_count += 1

        return fail_count

    def _extract_relations(self, instance, result):
        fail_count = 0

        for data in result["results"]:
            # Required fields
            rel_type = take_optional_field("type", data)
            source_id = take_optional_field("sourceId", data)
            target_id = take_optional_field("targetId", data)

            # Add tags to data
            if 'tags' in data and instance.tags:
                data['tags'] += instance.tags
            elif instance.tags:
                data['tags'] = instance.tags

            # We don't want to present all fields
            filtered_data = self._filter_fields(data)

            if rel_type is not None and source_id is not None and target_id is not None:
                self.relation(source_id, target_id, rel_type, filtered_data)
            else:
                fail_count += 1

        return fail_count

    def _filter_fields(self, data):
        result = dict()
        for key, value in data.items():
            if key not in self.EXCLUDE_FIELDS:
                result[key] = value
        return result

    def _auth_session(self, instance):
        """ This method is mocked for testing. Do not change its behavior """
        instance.splunkClient.auth_session()

    def _token_auth_session(self, instance, authentication, base_url, state):
        """ This method is mocked for testing. Do not change its behavior """
        result = instance.splunkClient.token_auth_session(authentication, base_url, state)
        self.commit_state(state)
        return result

    def _dispatch(self, instance, saved_search, splunk_user, splunk_app, _ignore_saved_search, parameters):
        """ This method is mocked for testing. Do not change its behavior """
        return instance.splunkClient.dispatch(saved_search, splunk_user, splunk_app, _ignore_saved_search, parameters)

    def _finalize_sid(self, instance, sid, saved_search):
        """ This method is mocked for testing. Do not change its behavior """
        return instance.splunkClient.finalize_sid(sid, saved_search)

    def load_state(self, instance):
        state = instance.get(self.STATE_FIELD_NAME)
        if state is None:
            state = {}
        return state

    def update_persistent_state(self, state, base_url, qualifier, data, action):
        """
        :param dictionary with the current persisted state
        :param base_url: base_url of the instance
        :param qualifier: a string used for making a unique key
        :param data: value of key
        :param action: action like add, remove or clear to perform

        This method persists the storage for the key when it is modified
        """
        key = base_url + qualifier if qualifier else base_url
        if action == 'remove':
            state.pop(key, None)
        elif action == 'clear':
            state.clear()
        else:
            state[key] = data
        self.commit_state(state)
