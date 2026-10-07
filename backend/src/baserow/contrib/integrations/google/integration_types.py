from baserow.contrib.integrations.oauth2.integration_types import (
    OAuth2IntegrationTypeMixin,
)
from baserow.core.integrations.registries import IntegrationType

from .models import GoogleIntegration


class GoogleIntegrationType(OAuth2IntegrationTypeMixin, IntegrationType):
    type = "google"
    model_class = GoogleIntegration

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"  # nosec B105
    account_info_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scopes = [
        "openid",
        "email",
        # Read and send: the email chat channel watches a label and replies
        # in the thread; sending alone is part of this scope.
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    # Google only issues a refresh token for offline access, and only on a
    # consent it actually shows; without `prompt=consent` a reconnect returns
    # no refresh token at all.
    extra_authorization_params = {"access_type": "offline", "prompt": "consent"}
