from rest_framework import serializers

from baserow_enterprise.api.sso.serializers import BaseSsoLoginRequestSerializer


class OIDCLoginRequestSerializer(BaseSsoLoginRequestSerializer):
    iss = serializers.CharField(
        required=True,
        help_text="Issuer to use for the authentication.",
    )
