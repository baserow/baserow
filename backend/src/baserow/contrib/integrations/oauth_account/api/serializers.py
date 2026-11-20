from rest_framework import serializers


class OAuthAccountConfigSerializer(serializers.Serializer):
    configured = serializers.BooleanField(
        help_text="Whether this installation can connect accounts of this "
        "provider without an OAuth client of the integration's own."
    )
    redirect_uri = serializers.CharField(
        help_text="The redirect URI to register with the provider's OAuth client."
    )
    allow_account_switch = serializers.BooleanField(
        help_text="Whether reconnecting may sign in as another account."
    )
    keep_connection_in_published_copies = serializers.BooleanField(
        help_text="Whether published applications and workflows keep a copy of "
        "the connection until they're published again."
    )


class OAuthAccountStartSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Creates an integration in this application once the sign-in "
        "completes.",
    )
    integration_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Or connects this integration again.",
    )
    service_types = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        default=list,
        max_length=20,
        help_text="The service types the account is connected for. The sign-in "
        "asks for the permissions they need.",
    )
    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="The name of the integration to create. Defaults to one with "
        "the account's email address.",
    )

    def validate(self, data):
        if (data["application_id"] is None) == (data["integration_id"] is None):
            raise serializers.ValidationError(
                "Exactly one of `application_id` and `integration_id` is required."
            )
        return data


class OAuthAccountStartResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()


class OAuthAccountCompleteSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=255)
    code = serializers.CharField(required=False, allow_blank=True, default="")
    error = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    error_description = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, default=""
    )


class OAuthAccountCompleteResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField(
        help_text="Whether the sign-in created the integration."
    )
    integration = serializers.DictField(help_text="The integration.")
