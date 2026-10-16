from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin

from ..validators import AGENT_TEXT_MAX_LENGTH


class AgentReadinessSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=["ready", "incomplete", "unavailable"])


class AgentConfigurationSerializer(AgentReadinessSerializer):
    name = serializers.CharField()
    instructions = serializers.CharField(allow_blank=True, trim_whitespace=False)
    provider_type = serializers.CharField(allow_null=True)
    model_identifier = serializers.CharField(allow_null=True)
    errors = serializers.DictField(
        child=serializers.ChoiceField(choices=["required", "unavailable"])
    )


class AgentConfigurationUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    name = serializers.CharField(max_length=160, required=False)
    instructions = serializers.CharField(
        max_length=AGENT_TEXT_MAX_LENGTH,
        allow_blank=True,
        trim_whitespace=False,
        required=False,
    )
    provider_type = serializers.CharField(
        max_length=255, allow_blank=True, allow_null=True, required=False
    )
    model_identifier = serializers.CharField(
        max_length=255, allow_blank=True, allow_null=True, required=False
    )
