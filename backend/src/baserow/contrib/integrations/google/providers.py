"""Google-specific configuration for the shared OAuth account implementation."""

from django.conf import settings

from baserow.contrib.integrations.oauth_account.exceptions import (
    OAuthFailed,
    ProviderUnavailable,
)
from baserow.contrib.integrations.oauth_account.providers import (
    REQUEST_EXCEPTIONS,
    AccountIdentity,
    OAuthClient,
    OAuthProvider,
)
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.fields import is_unreadable_secret

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GoogleOAuthProvider(OAuthProvider):
    name = "Google"
    base_scopes = ["openid", "email"]

    def get_instance_client(self):
        if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
            return OAuthClient(
                settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET
            )
        return None

    def get_client(self, integration=None):
        """Choose the saved custom Google client or the installation client."""
        if integration is not None and integration.client_mode == "custom":
            if (
                not integration.client_id
                or not integration.client_secret
                or is_unreadable_secret(integration.client_secret)
            ):
                return None
            return OAuthClient(integration.client_id, integration.client_secret)
        return self.get_instance_client()

    def get_authorization_endpoint(self, client):
        return "https://accounts.google.com/o/oauth2/v2/auth"

    def get_token_endpoint(self, client):
        return "https://oauth2.googleapis.com/token"

    def get_extra_authorization_params(self):
        return {
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }

    def normalize_scope(self, scope):
        # Google's response expands the OIDC alias used in the request.
        return (
            "https://www.googleapis.com/auth/userinfo.email"
            if scope == "email"
            else scope
        )

    def identify(self, client, token_set, deadline):
        """Resolve the verified Google identity without asking for mailbox read access."""
        try:
            response = send_http_request(
                method="GET",
                url="https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {token_set.access_token}"},
                deadline=deadline,
                allow_redirects=False,
                send_netrc_credentials=False,
            )
        except REQUEST_EXCEPTIONS as exc:
            raise ProviderUnavailable("Google could not be reached.") from exc
        try:
            identity = response.json()
        except ValueError:
            identity = None
        if (
            response.status_code != 200
            or not isinstance(identity, dict)
            or not isinstance(identity.get("sub"), str)
            or not isinstance(identity.get("email"), str)
            or identity.get("email_verified") is not True
        ):
            raise OAuthFailed("Google did not identify a verified account.")
        return AccountIdentity(
            account_id=identity["sub"],
            email=identity["email"],
            name=identity.get("name", ""),
            extra={"connected_client": client.fingerprint},
        )
