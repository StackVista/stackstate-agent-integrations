import logging
import os
import time
import typing
from typing import Self

import requests
import urllib3
from six import PY3

from stackstate_checks.splunk.config.splunk_instance_config_models import SavedSearchErrorBehavior

if PY3:
    from urllib.parse import urlencode, quote
else:
    from urllib import urlencode, quote

from urllib3.exceptions import InsecureRequestWarning
from requests.exceptions import HTTPError, ConnectionError, Timeout
from stackstate_checks.base.errors import CheckException
from stackstate_checks.splunk.client.splunk_jwt_auth import SplunkJWTAuth
from stackstate_checks.splunk.client.msft_jwt_auth import MsJWTAuth
from stackstate_checks.splunk.config import AuthType
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(InsecureRequestWarning)


class FinalizeException(Exception):
    """
       A custom exception for the finalize_sid method
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message


class TokenExpiredException(Exception):
    """
    A custom exception for the expired token
    """

    def __init__(self, message, code=None):
        self.message = message
        self.code = code


class LoggingRetry(Retry):
    def __init__(self, log, *args, **kwargs):
        self.log = log
        super(LoggingRetry, self).__init__(*args, **kwargs)

    def new(self, **kw: typing.Any) -> Self:
        return super(LoggingRetry, self).new(log=self.log, **kw)

    """
    A custom Retry class that intercepts the retry event to inject custom logging.
    """
    def increment(self, method=None, url=None, response=None, error=None, _pool=None, _stacktrace=None):
        self.log.warning(f"🔄 Retrying {method} request to {url}...")

        return super().increment(
            method=method,
            url=url,
            response=response,
            error=error,
            _pool=_pool,
            _stacktrace=_stacktrace
        )


class SplunkClient:

    def __init__(self, instance_config, *args, **kwargs):
        self.instance_config = instance_config
        self.log = logging.getLogger('%s' % __name__)
        self.requests_session = requests.session()
        self.jwt_adapter = None
        self.extra_header_name = None
        self.extra_header_value = None

        if os.getenv("SPLUNK_AUTH_EXTRA_HEADER_NAME"):
            self.extra_header_name = os.getenv("SPLUNK_AUTH_EXTRA_HEADER_NAME")
            if not os.getenv("SPLUNK_AUTH_EXTRA_HEADER_VALUE"):
                raise Exception(
                    "SPLUNK_AUTH_EXTRA_HEADER_VALUE is not set, while SPLUNK_AUTH_EXTRA_HEADER_NAME was set."
                )
            else:
                self.extra_header_value = os.getenv("SPLUNK_AUTH_EXTRA_HEADER_VALUE")

        if instance_config.auth_type == AuthType.TokenAuthMS:
            self.jwt_adapter = MsJWTAuth(instance_config)
        elif instance_config.auth_type == AuthType.TokenAuth:
            self.jwt_adapter = SplunkJWTAuth(instance_config, self._do_post)

        # Setup retries
        retry_strategy = LoggingRetry(
            log=self.log,
            total=instance_config.request_max_retry_count,
            backoff_factor=instance_config.request_retry_backoff_factor,
            status_forcelist=[500, 502, 503, 504],  # Only retryable 500s
            allowed_methods=["GET", "POST"],
            raise_on_status=False,  # Allow our code to handle the last produced issue.
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.requests_session.mount("http://", adapter)
        self.requests_session.mount("https://", adapter)

    def auth_session(self, committable_state):
        if self.instance_config.auth_type == AuthType.BasicAuth:
            self.log.debug("Using user/password based authentication mechanism")
            self._basic_auth()
        elif self.instance_config.auth_type == AuthType.TokenAuth:
            self.log.debug("Using token based authentication mechanism")
            self._token_auth_session(committable_state)
        elif self.instance_config.auth_type == AuthType.TokenAuthMS:
            self.log.debug("Using Micro$oft token based authentication mechanism")
            self._token_auth_session(committable_state)

    def _basic_auth(self):
        """
        retrieves a session token from Splunk to be used in subsequent requests
        session key expires after default 1 hour, configurable
        in Splunk: Settings -> Server -> General -> Session timeout
        Splunk returns the same key for the username/password combination.
        Side affecting function.
        An expired key results in a 401 Unauthorized response with content:
          {"messages":[{"type":"WARN","text":"call not properly authenticated"}]}%
        :return: nothing
        """
        auth_path = '/services/auth/login?output_mode=json'
        payload = urlencode([
            ('username', self.instance_config.auth_config.username),
            ('password', self.instance_config.auth_config.password),
            ('cookie', 1)], doseq=True)
        response = self._do_post(auth_path, payload, self.instance_config.default_request_timeout_seconds)
        response.raise_for_status()
        response_json = response.json()

        # Fallback mechanism in case no cookies were passed by splunk.
        session_key = response_json["sessionKey"]
        self.requests_session.headers.update({'Authentication': "Splunk %s" % session_key})
        self.add_extra_header()

    def _token_auth_session(self, committable_state):
        token = committable_state.get_auth_token()

        if token is None:
            token = self.jwt_adapter.get_initial_token()

        new_jwt_token = ""

        if self.jwt_adapter.is_token_expired(token):
            self.log.debug("Current in use authentication token is expired")
            msg = "Current in use authentication token is expired. Please provide a valid token in the YAML " \
                  "and restart the Agent"
            raise TokenExpiredException(msg)

        if self.jwt_adapter.token_needs_renewal(token):
            self.log.info("The token needs renewal as token is about to expire or this is initial token")
            new_jwt_token = self._create_auth_token(token)
            committable_state.set_auth_token(new_jwt_token)
        else:
            new_jwt_token = token

        self.requests_session.headers.update({'Authorization': "Bearer %s" % new_jwt_token})
        self.add_extra_header()

    def add_extra_header(self):
        if self.extra_header_name is not None:
            self.log.info("Adding static header `%s` to the request" % self.extra_header_name)
            self.requests_session.headers.update({self.extra_header_name: self.extra_header_value})

    def _create_auth_token(self, token):
        self.log.info("Creating a new authentication token")

        if token is not None:
            self.requests_session.headers.update({'Authorization': "Bearer %s" % token})

        return self.jwt_adapter.generate_token()

    def _get_saved_search_path(self, splunk_ns_user, splunk_app):
        return '/servicesNS/%s/%s/saved/searches/?output_mode=json&count=-1' % (
            splunk_ns_user, splunk_app
        )

    def saved_searches(self, splunk_app):
        """
        Retrieves a list of saved searches from splunk
        :return: list of names of saved searches
        """
        search_path = self._get_saved_search_path(self.instance_config.ns_user, splunk_app)

        response = self._do_get(search_path,
                                self.instance_config.default_request_timeout_seconds,
                                self.instance_config.verify_ssl_certificate)
        return response.json()["entry"]

    def _search_chunk(self, saved_search, search_id, offset, count):
        """
        Retrieves the results of an already running splunk search, identified by the given search id.
        :param saved_search: current SavedSearch being processed
        :param search_id: perform a search operation on the search id
        :param offset: starting offset, begin is 0, to start retrieving from
        :param count: the maximum number of elements expecting to be returned by the API call
        :return: raw json response from splunk
        """
        search_path = '/servicesNS/%s/%s/search/jobs/%s/results?output_mode=json&offset=%s&count=%s' % \
                      (self.instance_config.ns_user, saved_search.app, search_id, offset, count)

        response = self._do_get(search_path,
                                saved_search.request_timeout_seconds,
                                self.instance_config.verify_ssl_certificate)
        retry_count = 0

        # retry until information is available.
        while response.status_code == 204:  # HTTP No Content response
            self.log.debug(
                "Splunk has no result available yet for saved search {}. Going to retry".format(saved_search.name))
            if retry_count == saved_search.search_max_retry_count:
                raise CheckException(
                    "maximum retries reached for %s with saved search %s" %
                    (self.instance_config.base_url, saved_search.name))
            retry_count += 1
            time.sleep(saved_search.search_seconds_between_retries)
            response = self._do_get(search_path,
                                    saved_search.request_timeout_seconds,
                                    self.instance_config.verify_ssl_certificate)

        return response.json()

    def saved_search_results(self, search_id, saved_search):
        """
        Perform a saved search, returns a list of responses that were received
        """
        # fetch results in batches
        offset = 0
        nr_of_results = None
        results = []
        while nr_of_results is None or nr_of_results == saved_search.batch_size:
            response = self._search_chunk(saved_search, search_id, offset, saved_search.batch_size)
            # received a message?
            for message in response.get('messages', []):
                if message['type'] == "FATAL":
                    raise CheckException("Received FATAL exception from Splunk, got: " + message['text'])

            results.append(response)
            nr_of_results = len(response['results'])
            offset += nr_of_results
        return results

    def dispatch(self, saved_search, on_saved_search_error, parameters):
        """
        :param saved_search: The saved search to dispatch
        :param on_saved_search_error: Ignore saved search errors
        :param parameters: Parameters of the saved search
        :return: the sid of the saved search
        """
        dispatch_path = '/servicesNS/%s/%s/saved/searches/%s/dispatch?output_mode=json' % \
                        (self.instance_config.ns_user, saved_search.app, quote(saved_search.name))
        self.log.debug("Searching on Dispatch Path: " + dispatch_path)

        response_body = self._do_post(dispatch_path,
                                      parameters,
                                      saved_search.request_timeout_seconds,
                                      on_saved_search_error).json()

        return response_body.get("sid")

    def finalize_sid(self, search_id, saved_search):
        """
        :param search_id: The saved search id to finish
        :param saved_search: The saved search to finish
        """
        finish_path = '/services/search/jobs/%s/control?output_mode=json' % search_id
        payload = "action=finalize"

        try:
            res = self._do_post(finish_path,
                                payload,
                                saved_search.request_timeout_seconds,
                                on_saved_search_error=SavedSearchErrorBehavior.abort)
            # api returns 200 in general and even in case when saved search is already finalized
            if res.status_code == 200:
                self.log.info("Saved Search ID %s finished successfully." % search_id)
        # when api returns status code between 400 and 600, HTTPError will occur
        except HTTPError as error:
            # if status code except 404 throw error
            if error.response.status_code != 404:
                self.log.error("Search job not finalized and received response with status {} and body {}".format
                               (error.response.status_code, error.response.reason))
                raise FinalizeException(error.response.status_code, error.response.reason)
        # in case of timeout like read timeout or request timeout
        except Timeout as error:
            self.log.error("Search job not finalized as the timeout error occurred %s" % error)
            raise FinalizeException(None, str(error))
        # in case of network issue
        except ConnectionError as error:
            self.log.error("Search job not finalized as connection error occurred %s" % error)
            raise FinalizeException(None, str(error))

    def _do_get(self, path, request_timeout_seconds, verify_ssl_certificate):
        url = "%s%s" % (self.instance_config.base_url, path)
        response = self.requests_session.get(url, timeout=request_timeout_seconds, verify=verify_ssl_certificate)
        try:
            response.raise_for_status()
        except HTTPError as error:
            self.log.warning(
                "Received response with status {} and body {}".format(
                    response.status_code,
                    response.content))
            raise error
        return response

    def _do_post(self, path, payload, request_timeout_seconds, on_saved_search_error=SavedSearchErrorBehavior.ignore):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        url = "%s%s" % (self.instance_config.base_url, path)
        resp = self.requests_session.post(url,
                                          headers=headers,
                                          data=payload,
                                          timeout=request_timeout_seconds,
                                          verify=self.instance_config.verify_ssl_certificate)
        try:
            resp.raise_for_status()
        except HTTPError as error:
            if on_saved_search_error == SavedSearchErrorBehavior.abort:
                raise error
            self.log.warning("Received response with status {} and body {}".format(resp.status_code, resp.content))
        except Timeout as error:
            if on_saved_search_error == SavedSearchErrorBehavior.abort:
                self.log.error("Got a timeout error")
                raise error
            self.log.warning("Ignoring the timeout error as the flag on_saved_search_error is set to 'ignore'")
        except ConnectionError as error:
            if on_saved_search_error == SavedSearchErrorBehavior.abort:
                self.log.error(
                    "Received error response with status {} and body {}".format(resp.status_code, resp.content)
                )
                raise error
            self.log.warning("Ignoring the connection error as the flag on_saved_search_error is set to 'ignore'")
        return resp
