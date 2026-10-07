from typing import Optional

from baserow.contrib.integrations.oauth2.integration_types import (
    OAuth2IntegrationDict,
    OAuth2IntegrationTypeMixin,
)
from baserow.core.integrations.registries import IntegrationType

from .models import MicrosoftIntegration

LOGIN_URL = "https://login.microsoftonline.com"


class MicrosoftIntegrationDict(OAuth2IntegrationDict):
    tenant: str


class MicrosoftIntegrationType(OAuth2IntegrationTypeMixin, IntegrationType):
    type = "microsoft"
    model_class = MicrosoftIntegration
    SerializedDict = MicrosoftIntegrationDict

    account_info_url = "https://graph.microsoft.com/v1.0/me"
    scopes = [
        # Without it no refresh token is issued and the connection would
        # last an hour.
        "offline_access",
        "User.Read",
        "Mail.Send",
        # The email chat channel reads a folder and replies in its threads.
        "Mail.ReadWrite",
        "Calendars.ReadWrite",
        "ChannelMessage.Send",
    ]

    allowed_fields = [*OAuth2IntegrationTypeMixin.allowed_fields, "tenant"]
    request_serializer_field_names = [
        *OAuth2IntegrationTypeMixin.request_serializer_field_names,
        "tenant",
    ]
    serializer_field_names = [
        *OAuth2IntegrationTypeMixin.serializer_field_names,
        "tenant",
    ]
    # Tokens are issued per tenant as much as per app, so changing it also
    # requires the secret again (and disconnects, through the model).
    secret_field_dependencies = {"client_secret": ["client_id", "tenant"]}

    def get_authorization_url(self, integration) -> str:
        return f"{LOGIN_URL}/{integration.tenant or 'common'}/oauth2/v2.0/authorize"

    def get_token_url(self, integration) -> str:
        return f"{LOGIN_URL}/{integration.tenant or 'common'}/oauth2/v2.0/token"

    def extract_account_email(self, body: dict) -> Optional[str]:
        return body.get("mail") or body.get("userPrincipalName")
