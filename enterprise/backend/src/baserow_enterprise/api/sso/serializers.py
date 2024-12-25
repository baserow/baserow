from typing import Dict
from urllib.parse import urlparse

from rest_framework import serializers

from baserow.api.user.serializers import NormalizedEmailField
from baserow.api.user.validators import language_validation


class BaseSsoLoginRequestSerializer(serializers.Serializer):
    email = NormalizedEmailField(
        required=False, help_text="The email address of the user."
    )
    original = serializers.CharField(
        required=False,
        help_text="The original URL that the user wanted to access.",
    )
    language = serializers.CharField(
        required=False,
        min_length=2,
        max_length=10,
        validators=[language_validation],
        help_text="An ISO 639 language code (with optional variant) "
        "selected by the user. Ex: en-GB.",
    )

    def to_internal_value(self, instance) -> Dict[str, str]:
        data = super().to_internal_value(instance)
        return {k: v for k, v in data.items() if v is not None}


class SsoLoginRequestSerializer(BaseSsoLoginRequestSerializer):
    workspace_invitation_token = serializers.CharField(
        required=False,
        help_text="If provided and valid, the user accepts the workspace invitation and"
        " will have access to the workspace after login or signing up.",
    )

    def validate_original(self, value):
        """Only relative URLs are allowed."""

        if urlparse(value).hostname:
            return None

        return value
