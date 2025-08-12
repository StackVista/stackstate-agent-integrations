class SplunkJWTAuth:

    def __init__(self):
        return None

    def _current_time(self):
        """ This method is mocked for testing. Do not change its behavior """
        return datetime.datetime.utcnow()

    def generate_token(self):
        self.log.debug("Creating a new authentication token")
        token_path = '/services/authorization/tokens?output_mode=json'
        name = self.instance_config.name
        audience = self.instance_config.audience
        expiry_days = self.instance_config.token_expiration_days
        payload = {'name': name, 'audience': audience, 'expires_on': "+{}d".format(str(expiry_days))}
        self.requests_session.headers.update({'Authorization': "Bearer %s" % token})
        response = self._do_post(token_path, payload, self.instance_config.default_request_timeout_seconds)
        response.raise_for_status()
        response_json = response.json()

        new_token = response_json.get("entry")[0].get("content").get("token")
        return new_token 

    def is_token_expired(self, token, renewal_days, is_initial_token=False):
        """
        Method to check if the token is expired or not.
        We treat a token needing renewal as an expired one.
        :param token: the token used for validation
        :param is_initial_token: boolean flag if it is first initial token, default is False
        :return: boolean flag if token is valid or not
        """
        current_time = self._current_time()
        decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=['HS512'])
        expiry_time = decoded_token.get("exp")
        if expiry_time == 0 and is_initial_token:
            self.log.warning("Initial token provided in the configuration doesn't have an expiration value.")
            return False
        expiry_date = datetime.datetime.fromtimestamp(expiry_time)
        days = (expiry_date.date() - current_time.date()).days
        days = self._decode_token_util(token, is_initial_token)
        return True if days < renewal_days or is_initial_token else False
