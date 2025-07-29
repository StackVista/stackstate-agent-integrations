# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import logging
import os

from requests import Session, Timeout

from stackstate_checks.dynatrace.custom_auth import MsJWTAuth


class _DynatraceClient:

    def __init__(self, token, verify=False, cert=None, keyfile=None, timeout=None):
        """
        Client for Dynatrace rest API. It's used by dynatrace_topology and dynatrace_health check.
        :param token: token from Dynatrace platform which has access to read the API endpoints
        :param verify: verify the https certificate
        :param cert: path to certificate file for https verification
        :param keyfile: path to public key of certificate for https verification
        :param timeout: request timeout in seconds
        """
        self.token = token
        self.verify = verify
        self.cert = cert
        self.keyfile = keyfile
        self.timeout = timeout
        self.log = logging.getLogger(__name__)

    def get_dynatrace_json_response(self, endpoint, params=None):
        """
        Gets response from Dynatrace endpoint
        :param endpoint: Drynatrace API endpoint
        :param params: request params dictionary
        :return: dictionary from API json response
        """
        headers = {"Authorization": "Api-Token %s" % self.token}
        try:
            with Session() as session:
                session.headers.update(headers)
                session.verify = self.verify
                if self.cert:
                    session.cert = (self.cert, self.keyfile)
                response = session.get(endpoint, params=params, timeout=self.timeout)
                response_json = response.json()
                if response.status_code != 200:
                    if "error" in response_json:
                        msg = response_json["error"].get("message")
                    else:
                        msg = "Got %s when hitting %s" % (response.status_code, endpoint)
                    self.log.error(msg)
                    raise Exception(
                        'Got an unexpected error with status code %s and message: %s' % (response.status_code, msg))
                return response_json
        except Timeout:
            msg = "%d seconds timeout" % self.timeout
            self.log.error(msg)
            raise Exception("Timeout exception occurred for endpoint %s with message: %s" % (endpoint, msg))

    def get_endpoint(self, url, path):
        """
        Creates the API endpoint from the path
        :param url: the URL from conf.yaml
        :param path: the rest of the path of the specific dynatrace endpoint
        :return: the full url of the endpoint
        """
        sanitized_url = url[:-1] if url.endswith("/") else url
        sanitized_path = path[1:] if path.startswith("/") else path
        endpoint = sanitized_url + "/" + sanitized_path
        self.log.debug("Dynatrace URL endpoint %s", endpoint)
        return endpoint

    def get_token(self):
        return self.token


class DynatraceClientFactory:
    def __init__(self):
        self._instances = {}
        self._ms_jwt_auth = None

    def create_client(self, instance_name, token, verify=False, cert=None, keyfile=None, timeout=None):
        is_jwt_auth = os.getenv('JWT_AUTH', 'false').lower() == 'true'
        if is_jwt_auth:
            if not self._ms_jwt_auth:
                self._ms_jwt_auth = MsJWTAuth(verify, cert, keyfile, timeout)
            token = self._ms_jwt_auth.get_token()

        if instance_name not in self._instances:
            client = _DynatraceClient(token, verify, cert, keyfile, timeout)
            self._instances[instance_name] = client
        # Always update the token in case it has been renewed
        self._instances[instance_name].token = token
        return self._instances[instance_name]
