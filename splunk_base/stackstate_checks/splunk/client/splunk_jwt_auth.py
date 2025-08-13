import logging
import os
from datetime import datetime, timezone
import jwt
import requests

class SplunkJWTAuth:

    def __init__(self, instance_config, get_current_time, post_fn):
        # Passing time function from the outside for easier mocking and integration
        self.log = logging.getLogger('%s' % __name__)
        self.instance_config = instance_config
        self._get_current_time = get_current_time
        self._do_post = post_fn

    def _get_renewal_days(self, token, is_initial_token=False):
        current_time = self._get_current_time()
        decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=['HS512'])
        expiry_time = decoded_token.get("exp")
        if expiry_time == 0 and is_initial_token:
            self.log.warning("Initial token provided in the configuration doesn't have an expiration value.")
            return False
        expiry_date = datetime.fromtimestamp(expiry_time)
        days = (expiry_date.date() - current_time.date()).days
        return days

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

    def token_needs_renewal(self, token, renewal_days, is_initial_token):
        days = self._get_renewal_days(token, is_initial_token)
        if days <= renewal_days or is_initial_token:
            return True
        else:
            return False

    def is_token_expired(self, token, is_initial_token=False):
        days = self._get_renewal_days(token, is_initial_token)
        return True if days < 0 else False
