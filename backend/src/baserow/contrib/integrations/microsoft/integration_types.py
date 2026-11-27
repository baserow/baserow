from rest_framework import serializers

from baserow.contrib.integrations.oauth_account.integration_types import (
    OAuthAccountIntegrationDict,
    OAuthAccountIntegrationTypeMixin,
)
from baserow.core.integrations.registries import IntegrationType

from .models import MicrosoftIntegration
from .provider import MicrosoftProvider


class MicrosoftIntegrationType(OAuthAccountIntegrationTypeMixin, IntegrationType):
    """
    A Microsoft account, connected by signing in with Microsoft through the
    OAuth account endpoints, never by sending tokens to the integration API.
    """

    type = "microsoft"
    model_class = MicrosoftIntegration
    provider = MicrosoftProvider()

    class SerializedDict(OAuthAccountIntegrationDict):
        tenant_id: str

    serializer_field_names = [
        *OAuthAccountIntegrationTypeMixin.serializer_field_names,
        "account_type",
    ]
    serializer_field_overrides = {
        **OAuthAccountIntegrationTypeMixin.serializer_field_overrides,
        "account_type": serializers.CharField(
            read_only=True,
            help_text="`work_or_school`, `personal`, or empty before the first "
            "sign-in.",
        ),
    }
