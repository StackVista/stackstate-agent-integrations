import datetime
import logging

from enum import Enum
from iso8601 import iso8601
from pytz import timezone
from stackstate_checks.base.errors import CheckException

AUTH_TOKEN_KEY = "auth_token"
SID_KEY_BASE = "sid"


class SplunkPersistentState(object):
    """
    Helper class to abstract away state that can be committed. Exposes data an a commit function
    """

    def __init__(self, persistent_state):
        self.state = persistent_state

    def get_auth_token(self):
        return self.state.get(AUTH_TOKEN_KEY)

    def set_auth_token(self, token):
        self.state[AUTH_TOKEN_KEY] = token

    def _search_key(self, search_name):
        return "%s_%s" % (SID_KEY_BASE, search_name)

    def get_sid(self, search_name):
        return self.state.get(self._search_key(search_name))

    def set_sid(self, search_name, sid):
        self.state[self._search_key(search_name)] = sid

    def remove_sid(self, search_name):
        self.state.pop(self._search_key(search_name), None)


class AuthType(Enum):
    BasicAuth = "BasicAuth"
    TokenAuth = "TokenAuth"


class SplunkInstanceConfig(object):
    def __init__(self, instance, init_config, defaults):
        self.log = logging.getLogger('%s' % __name__)

        self.defaults = defaults
        self.init_config = init_config

        self.default_request_timeout_seconds = self.get_or_default('default_request_timeout_seconds')
        self.default_search_max_retry_count = self.get_or_default('default_search_max_retry_count')
        self.default_search_seconds_between_retries = self.get_or_default('default_search_seconds_between_retries')
        self.default_verify_ssl_certificate = self.get_or_default('default_verify_ssl_certificate')
        self.default_batch_size = self.get_or_default('default_batch_size')
        self.default_saved_searches_parallel = self.get_or_default('default_saved_searches_parallel')
        self.default_app = self.get_or_default('default_app')
        self.default_parameters = self.get_or_default('default_parameters')

        self.verify_ssl_certificate = bool(instance.get('verify_ssl_certificate', self.default_verify_ssl_certificate))

        if 'url' not in instance:
            raise CheckException('Instance is missing "url" value.')
        self.base_url = instance['url']

        if 'authentication' in instance:
            authentication = instance["authentication"]
            if 'token_auth' in authentication and authentication.token_auth is not None:
                token_auth = authentication["token_auth"]
                if 'name' not in token_auth:
                    raise CheckException('Instance missing "authentication.token_auth.name" value')
                if 'initial_token' not in token_auth:
                    raise CheckException('Instance missing "authentication.token_auth.initial_token" '
                                         'value')
                if 'audience' not in token_auth:
                    raise CheckException('Instance missing "authentication.token_auth.audience" value')
                self.auth_type = AuthType.TokenAuth
                self.audience = token_auth.get("audience")
                self.initial_token = token_auth.get("initial_token")
                self.name = token_auth.get("name")
                self.token_expiration_days = token_auth.get("token_expiration_days", 90)
                self.renewal_days = token_auth.get("renewal_days", 10)
            elif 'basic_auth' in authentication and authentication.basic_auth is not None:
                basic_auth = authentication["basic_auth"]
                if 'username' not in basic_auth:
                    raise CheckException('Instance missing "authentication.basic_auth.username" value')
                if 'password' not in basic_auth:
                    raise CheckException('Instance missing "authentication.basic_auth.password" value')
                self.auth_type = AuthType.BasicAuth
                self.username = basic_auth.get("username")
                self.password = basic_auth.get("password")
            else:
                raise CheckException('Instance missing "authentication.basic_auth" or '
                                     '"authentication.token_auth" value')
        else:
            if instance.get('username') is not None and instance.get('password') is not None:
                self.log.warning("This username and password configuration will be deprecated soon. Please use the new "
                                 "updated configuration from the conf")
                self.username = instance.get('username')
                self.password = instance.get('password')
                self.auth_type = AuthType.BasicAuth
            else:
                raise CheckException("Instance missing 'authentication'.")

        self.ignore_saved_search_errors = instance.get('ignore_saved_search_errors', False)
        self.saved_searches_parallel = int(
            instance.get('saved_searches_parallel', self.default_saved_searches_parallel))
        self.tags = instance.get('tags', [])

    def get_or_default(self, field):
        return self.init_config.get(field, self.defaults[field])

    def get_auth_tuple(self):
        return self.username, self.password


class SplunkSavedSearch(object):
    def __init__(self, instance_config, saved_search_instance):
        if "name" in saved_search_instance:
            self.name = saved_search_instance['name']
            self.match = None
        elif "match" in saved_search_instance:
            self.match = saved_search_instance['match']
            self.name = None
        else:
            raise Exception("Neither 'name' or 'match' should be defined for saved search.")

        # maps from fields (as they go to output) to corresponding column names in results we get from Splunk
        self.critical_fields = None  # if absent, then fail the search
        self.required_fields = None  # if absent, then drop the item and continue with other items in this search
        self.optional_fields = None  # allowed to be absent
        self.fixed_fields = None  # fields that are filled in by the check

        self.parameters = self._saved_search_instance_get_or_else(
            saved_search_instance, dict, "parameters", instance_config.default_parameters)

        self.request_timeout_seconds = self._saved_search_instance_get_or_else(
            saved_search_instance, int, "request_timeout_seconds", instance_config.default_request_timeout_seconds)

        self.search_max_retry_count = self._saved_search_instance_get_or_else(
            saved_search_instance, int, "search_max_retry_count", instance_config.default_search_max_retry_count)

        self.search_seconds_between_retries = self._saved_search_instance_get_or_else(
            saved_search_instance, int, "search_seconds_between_retries", instance_config.default_search_seconds_between_retries)

        self.batch_size = self._saved_search_instance_get_or_else(
            saved_search_instance, int, "batch_size", instance_config.default_batch_size)

        self.app = saved_search_instance.get("app", instance_config.default_app)

    # Attempt to find a key in saved_search_instance and if not found return a default
    # None inside the dictionaries will also be seen as invalid and return the alternative
    @staticmethod
    def _saved_search_instance_get_or_else(saved_search_instance, cast_to_type, key, alternative):
        parameters = saved_search_instance.get(key)

        if parameters is not None:
            return cast_to_type(parameters)
        else:
            return cast_to_type(alternative)

    def retrieve_fields(self, data):
        retrieved_data = {}

        # Critical fields - escalate any exceptions if missing a field
        if self.critical_fields:
            retrieved_data.update({
                field: take_required_field(field_column, data)
                for field, field_column in self.critical_fields.items()
            })

        # Required fields - catch exceptions if missing a field
        try:
            if self.required_fields:
                retrieved_data.update({
                    field: take_required_field(field_column, data)
                    for field, field_column in self.required_fields.items()
                })
        except CheckException as e:
            raise LookupError(e)  # drop this item, but continue with next

        # Optional fields
        if self.optional_fields:
            retrieved_data.update({
                field: take_optional_field(field_column, data)
                for field, field_column in self.optional_fields.items()
            })

        # Fixed fields
        if self.fixed_fields:
            retrieved_data.update(self.fixed_fields)

        return retrieved_data


# TODO: Move this code once we move the telemetry splunk plugins
class SplunkTelemetryInstanceConfig(SplunkInstanceConfig):
    def __init__(self, instance, init_config, defaults):
        super(SplunkTelemetryInstanceConfig, self).__init__(instance, init_config, defaults)

        self.default_unique_key_fields = self.get_or_default('default_unique_key_fields')


def take_required_field(field, obj):
    """
    Get a field form an object, remove its value and remove the field form the object
    """
    if field not in obj:
        raise CheckException("Missing '%s' field in result data" % field)
    value = obj[field]
    del obj[field]
    return value


def take_optional_field(field, obj):
    """
    Get a field form an object, remove its value and remove the field form the object
    """
    if field not in obj:
        return None
    value = obj[field]
    del obj[field]
    return value


def get_utc_time(seconds):
    return datetime.datetime.utcfromtimestamp(seconds).replace(tzinfo=timezone("UTC"))


def get_time_since_epoch(utc_datetime):
    begin_epoch = get_utc_time(0)
    timestamp = (utc_datetime - begin_epoch).total_seconds()
    return timestamp


def time_to_seconds(str_datetime_utc):
    """
    Converts time in utc format 2016-06-27T14:26:30.000+00:00 to seconds
    """
    parsed_datetime = iso8601.parse_date(str_datetime_utc)
    return get_time_since_epoch(parsed_datetime)
