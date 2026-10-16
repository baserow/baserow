from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.pagination import PageNumberPagination

from ..models import AgentConversation, AgentMessage
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


class AgentConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConversation
        fields = (
            "uuid",
            "title",
            "source_type",
            "visibility",
            "created_on",
            "updated_on",
        )


class AgentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentMessage
        fields = ("id", "uuid", "role", "content", "created_on")


class AgentMessageContentSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    content = serializers.CharField(
        max_length=AGENT_TEXT_MAX_LENGTH, trim_whitespace=False
    )

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "This field may not be blank.", code="blank"
            )
        return value


class AgentConversationCreateSerializer(AgentMessageContentSerializer):
    uuid = serializers.UUIDField()
    message_uuid = serializers.UUIDField()


class AgentMessageCreateSerializer(AgentMessageContentSerializer):
    uuid = serializers.UUIDField()


class AgentMessageCreatedSerializer(serializers.Serializer):
    conversation = AgentConversationSerializer()
    message = AgentMessageSerializer()


class AgentConversationPagination(PageNumberPagination):
    page_size = 20


class AgentMessagePagination(PageNumberPagination):
    page_size = 50
