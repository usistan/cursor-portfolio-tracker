"""E*TRADE OAuth 1.0a mit wählbarem Sandbox- vs. Produktions-Host.

Die Bibliothek ``pyetrade`` nutzt für ``ETradeOAuth`` fest eingebaute
``https://api.etrade.com/...``-URLs. Sandbox-Consumer-Keys müssen dagegen
``https://apisb.etrade.com/oauth/...`` verwenden, sonst: oauth_problem=consumer_key_rejected.
"""

from __future__ import annotations

import logging

from requests_oauthlib import OAuth1Session

LOGGER = logging.getLogger(__name__)

# Autorisierungsseite (Browser) — laut E*TRADE-Dokumentation für den OAuth-Flow
AUTH_AUTHORIZE_URL = "https://us.etrade.com/e/t/etws/authorize"


def oauth_api_base(sandbox: bool) -> str:
    return "https://apisb.etrade.com" if sandbox else "https://api.etrade.com"


class EtradeOAuth:
    """Entspricht dem Ablauf von ``pyetrade.ETradeOAuth``, mit ``sandbox``-Schalter."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        *,
        sandbox: bool,
        callback_url: str = "oob",
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.sandbox = sandbox
        self.callback_url = callback_url
        base = oauth_api_base(sandbox)
        self.req_token_url = f"{base}/oauth/request_token"
        self.access_token_url = f"{base}/oauth/access_token"
        self.session: OAuth1Session | None = None
        self.access_token = None
        self.resource_owner_key = None

    def get_request_token(self) -> str:
        self.session = OAuth1Session(
            self.consumer_key,
            self.consumer_secret,
            callback_uri=self.callback_url,
            signature_type="AUTH_HEADER",
        )
        self.session.fetch_request_token(self.req_token_url)
        authorization_url = self.session.authorization_url(AUTH_AUTHORIZE_URL)
        akey = self.session.parse_authorization_response(authorization_url)
        self.resource_owner_key = akey["oauth_token"]
        formated_auth_url = "%s?key=%s&token=%s" % (
            AUTH_AUTHORIZE_URL,
            self.consumer_key,
            akey["oauth_token"],
        )
        LOGGER.debug(formated_auth_url)
        return formated_auth_url

    def get_access_token(self, verifier: str) -> dict:
        if self.session is None:
            raise RuntimeError("get_request_token muss zuerst aufgerufen werden.")
        self.session._client.client.verifier = verifier
        self.access_token = self.session.fetch_access_token(self.access_token_url)
        LOGGER.debug(self.access_token)
        return self.access_token
