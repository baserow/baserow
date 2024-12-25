from rest_framework import serializers

from baserow_enterprise.api.sso.saml.serializers import SAMLResponseSerializer
from baserow_enterprise.api.sso.serializers import BaseSsoLoginRequestSerializer


class CommonSsoLoginRequestSerializer(BaseSsoLoginRequestSerializer):
    next = serializers.CharField(
        required=False,
        help_text="If provided, the user will be redirected to that path after login",
    )


class CommonSAMLResponseSerializer(SAMLResponseSerializer):
    query_param_serializer = CommonSsoLoginRequestSerializer
