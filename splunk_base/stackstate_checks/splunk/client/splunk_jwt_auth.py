import logging
import os
from datetime import datetime, timezone
import jwt
import requests


class SplunkJWTAuth:

    NO_EXPIRY = 365

    def __init__(self, instance_config, post_fn):
        self.log = logging.getLogger('%s' % __name__)
        self.instance_config = instance_config
        if not os.getenv("SPLUNK_AUTH_JWT_INITIAL_TOKEN", self.instance_config.initial_token):
            raise Exception("SPLUNK_AUTH_JWT_INITIAL_TOKEN is not set, please specify the value through the SPLUNK_AUTH_JWT_INITIAL_TOKEN or instance_config.initial_token .")
        self.initial_token = os.getenv("SPLUNK_AUTH_JWT_INITIAL_TOKEN", self.instance_config.initial_token)
        self._do_post = post_fn

    def _current_time(self):
        """ This method is mocked for testing. Do not change its behavior """
        return datetime.utcnow()

    def _get_renewal_days(self, token):
        current_time = self._current_time()
        decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=['HS512'])
        expiry_time = decoded_token.get("exp")

        if expiry_time == 0 and token == self.initial_token:
            self.log.warning("Initial token provided in the configuration doesn't have an expiration value. Using initial_token as JWT token")
            return SplunkJWTAuth.NO_EXPIRY

        expiry_date = datetime.fromtimestamp(expiry_time)
        days = (expiry_date.date() - current_time.date()).days
        return days

    def get_initial_token(self):
        self.log.info("Using initial token for splunk JWT authentication.")
        return self.initial_token

    def generate_token(self):
        self.log.debug("Creating a new authentication token")
        token_path = '/services/authorization/tokens?output_mode=json'
        name = self.instance_config.name
        audience = self.instance_config.audience
        expiry_days = self.instance_config.token_expiration_days
        payload = {'name': name, 'audience': audience, 'expires_on': "+{}d".format(str(expiry_days))}
        response = self._do_post(token_path, payload, self.instance_config.default_request_timeout_seconds)
        response.raise_for_status()
        response_json = response.json()

        new_token = response_json.get("entry")[0].get("content").get("token")
        return new_token

    def token_needs_renewal(self, token, renewal_days):
        days = self._get_renewal_days(token)
        self.log.error(f"Checking if token needs renewal. Time left: {days:.2f} days")
        if days <= renewal_days and days != SplunkJWTAuth.NO_EXPIRY:
            return True
        else:
            return False

    def is_token_expired(self, token):
        days = self._get_renewal_days(token)
        return True if days < 0 else False
