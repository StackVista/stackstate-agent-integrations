import logging
import os
from datetime import datetime, timezone
import jwt
import requests


class MsJWTAuth:

    def __init__(self, verify=False, cert=None, keyfile=None, timeout=None):
        self.verify = verify
        self.cert = cert
        self.keyfile = keyfile
        self.timeout = timeout
        self.log = logging.getLogger(__name__)
        self._token = None
        self._token_expiry = datetime.min.replace(tzinfo=timezone.utc)

        # --- MS vars prep ---
        self.MICROSOFT_TENANT_ID = os.getenv("TENANT_ID")
        self.MICROSOFT_CLIENT_ID = os.getenv("CLIENT_ID")
        self.MICROSOFT_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
        self.MICROSOFT_RENEWAL_MINUTES = int(os.getenv("RENEWAL_MINUTES", 10))
        self.MICROSOFT_SCOPE = os.getenv("SCOPE")

        # Validate required environment variables
        if not self.MICROSOFT_TENANT_ID:
            raise ValueError("TENANT_ID environment variable is required")
        if not self.MICROSOFT_CLIENT_ID:
            raise ValueError("CLIENT_ID environment variable is required")
        if not self.MICROSOFT_CLIENT_SECRET:
            raise ValueError("CLIENT_SECRET environment variable is required")
        if not self.MICROSOFT_SCOPE:
            raise ValueError("SCOPE environment variable is required")

    def get_token(self):
        """
        Returns a valid Microsoft JWT, renewing it if necessary.
        """
        if self._is_token_expired():
            self._generate_microsoft_token()
        return self._token

    def _generate_microsoft_token(self):
        self.log.info("Generating new Microsoft token")
        microsoft_url = f"https://login.microsoftonline.com/{self.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
        microsoft_payload = {
            "grant_type": "client_credentials",
            "client_id": self.MICROSOFT_CLIENT_ID,
            "client_secret": self.MICROSOFT_CLIENT_SECRET,
            "scope": self.MICROSOFT_SCOPE,
        }
        microsoft_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            self.log.debug(f"Requesting token from: {microsoft_url}")
            self.log.debug(f"Client ID: {self.MICROSOFT_CLIENT_ID}")
            self.log.debug(f"Scope: {self.MICROSOFT_SCOPE}")

            response = requests.post(microsoft_url, data=microsoft_payload, headers=microsoft_headers,
                                     verify=self.verify,
                                     cert=(self.cert, self.keyfile) if self.cert else None, timeout=self.timeout)
            response.raise_for_status()

            response_json = response.json()
            self._token = response_json.get("access_token")

            if not self._token:
                raise Exception("No access_token found in response")

            self.log.info("Successfully generated Microsoft token")

        except requests.exceptions.RequestException as e:
            self.log.error(f"Failed to generate Microsoft token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.log.error(f"Response status: {e.response.status_code}")
                self.log.error(f"Response body: {e.response.text}")
            raise
        except Exception as e:
            self.log.error(f"Unexpected error generating Microsoft token: {e}")
            raise

        # Decode the token to get the expiry time
        # Signature and audience verification can be enabled through environment variables,
        # but are disabled by default.
        verify_signature_str = os.getenv('JWT_VERIFY_SIGNATURE', 'false')
        verify_signature = verify_signature_str.lower() == 'true'

        verify_audience_str = os.getenv('JWT_VERIFY_AUDIENCE', 'false')
        verify_audience = verify_audience_str.lower() == 'true'

        try:
            # Azure AD tokens use RS256 algorithm, not HS512
            decoded_token = jwt.decode(self._token, options={"verify_signature": verify_signature,
                                                             "verify_aud": verify_audience},
                                       algorithms=['RS256'])
            expiry = decoded_token.get("exp")

            if expiry:
                self._token_expiry = datetime.fromtimestamp(expiry, timezone.utc)
            else:
                self.log.warning("No expiry found in token, setting default expiry")
                self._token_expiry = datetime.now(timezone.utc)
        except jwt.InvalidTokenError as e:
            self.log.error(f"Failed to decode JWT token: {e}")
            # Fallback: set a default expiry time
            self._token_expiry = datetime.now(timezone.utc)

    def _is_token_expired(self):
        if not self._token:
            return True

        current_time = datetime.now(timezone.utc)
        time_difference = self._token_expiry - current_time
        expiry_minutes = time_difference.total_seconds() / 60
        self.log.info(f"Checking if Microsoft token needs renewal. Time left: {expiry_minutes:.2f} minutes")

        if expiry_minutes < self.MICROSOFT_RENEWAL_MINUTES:
            self.log.info("Token has expired or is nearing expiration. Renewing.")
            return True
        else:
            self.log.info(f"Token is still valid for {expiry_minutes:.2f} minutes.")
            return False
