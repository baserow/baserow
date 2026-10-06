from rest_framework import serializers


class OAuth2AuthorizeRequestSerializer(serializers.Serializer):
    return_url = serializers.URLField(
        help_text="The frontend page the browser returns to once the provider "
        "has answered; it receives `oauth2_status` and `oauth2_integration` query "
        "parameters."
    )


class OAuth2AuthorizeResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField(
        help_text="The provider's consent page to send the browser to."
    )
