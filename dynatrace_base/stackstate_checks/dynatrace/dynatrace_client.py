# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import logging
import os
from collections import defaultdict

from requests import Session, Timeout

from stackstate_checks.dynatrace.custom_auth import MsJWTAuth


class _DynatraceClient:

    def __init__(self, token, verify=False, cert=None, keyfile=None, timeout=None, is_jwt_auth=False):
        """
        Client for Dynatrace rest API. It's used by dynatrace_topology and dynatrace_health check.
        :param token: token from Dynatrace platform which has access to read the API endpoints
        :param verify: verify the https certificate
        :param cert: path to certificate file for https verification
        :param keyfile: path to public key of certificate for https verification
        :param timeout: request timeout in seconds
        :param is_jwt_auth: whether this is using JWT authentication
        """
        self.token = token
        self.verify = verify
        self.cert = cert
        self.keyfile = keyfile
        self.timeout = timeout
        self.is_jwt_auth = is_jwt_auth
        self.log = logging.getLogger(__name__)
        # Track 404 occurrences per entity type to avoid spam and provide summary
        self._entity_404_counts = defaultdict(int)
        self._entity_404_logged = set()

    def get_dynatrace_json_response(self, endpoint, params=None):
        """
        Gets response from Dynatrace endpoint
        :param endpoint: Drynatrace API endpoint
        :param params: request params dictionary
        :return: dictionary from API json response
        """
        # Use Bearer for JWT tokens, Api-Token for API tokens
        if self.is_jwt_auth:
            headers = {"Authorization": "Bearer %s" % self.token}
        else:
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

                    # Handle 404s for all entity types with smart logging and counting
                    if (
                        response.status_code == 404
                        and "/api/v2/entities/" in endpoint
                    ):
                        self._handle_entity_404(endpoint, msg)
                    else:
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

    def _handle_entity_404(self, endpoint, msg):
        """
        Handle 404 errors for entity endpoints with smart logging and counting.
        Logs each entity type 404 only once at INFO level and keeps count of occurrences.

        :param endpoint: The endpoint that returned 404
        :param msg: The error message to log
        """
        try:
            # Extract entity ID from endpoint
            entity_id_part = endpoint.split("/api/v2/entities/")[1]
            entity_id = entity_id_part.split("?")[0]

            # Extract entity type (part before the hyphen)
            if "-" in entity_id:
                entity_type = entity_id.split("-")[0]
            else:
                entity_type = "UNKNOWN"

            # Increment count for this entity type
            self._entity_404_counts[entity_type] += 1

            # Log only the first occurrence for each entity type at INFO level
            if entity_type not in self._entity_404_logged:
                self.log.info(
                    "Entity type %s returned 404 (first occurrence). "
                    "This message will not be repeated. Count: %d. Endpoint: %s",
                    entity_type, self._entity_404_counts[entity_type], endpoint
                )
                self._entity_404_logged.add(entity_type)

        except Exception:
            # Fallback: if parsing fails, log as info level without counting
            self.log.info("Entity 404 error (parsing failed): %s", msg)

    def get_entity_404_summary(self):
        """
        Get a summary of all 404 errors encountered by entity type.

        :return: Dictionary with entity types as keys and counts as values
        """
        return dict(self._entity_404_counts)

    def log_entity_404_summary(self):
        """
        Log a summary of all 404 errors encountered, if any.
        """
        if self._entity_404_counts:
            summary_lines = []
            total_404s = sum(self._entity_404_counts.values())
            summary_lines.append(f"Summary: {total_404s} total 404 errors across {len(self._entity_404_counts)} "
                                 f"entity types:")

            # Sort by count (descending) for better readability
            sorted_counts = sorted(self._entity_404_counts.items(), key=lambda x: x[1], reverse=True)
            for entity_type, count in sorted_counts:
                summary_lines.append(f"  {entity_type}: {count} occurrences")

            self.log.info("\n".join(summary_lines))

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
            client = _DynatraceClient(token, verify, cert, keyfile, timeout, is_jwt_auth)
            self._instances[instance_name] = client
        # Always update the token in case it has been renewed
        self._instances[instance_name].token = token
        self._instances[instance_name].is_jwt_auth = is_jwt_auth
        return self._instances[instance_name]
