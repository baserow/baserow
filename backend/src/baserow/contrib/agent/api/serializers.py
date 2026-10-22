from typing import get_args
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.pagination import PageNumberPagination
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentTurn,
)
from baserow.contrib.agent.types import AgentReadinessState
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH


READINESS_CHOICES = get_args(AgentReadinessState)


class AgentApplicationSerializer(serializers.ModelSerializer):
    readiness = serializers.SerializerMethodField(
        help_text="Whether the agent's configuration is complete and its model is enabled."
    )

    class Meta:
        model = AgentApplication
        fields = ("name", "readiness")

    @extend_schema_field(serializers.ChoiceField(choices=READINESS_CHOICES))
    def get_readiness(self, instance: AgentApplication) -> AgentReadinessState:
        """
        Compute the readiness without exposing the configuration values.

        :param instance: The Agent being serialized.
        :return: The readiness of the Agent.
        """

        # List views pass provider states so they aren't loaded per workspace.
        provider_state = self.context.get("ai_provider_states", {}).get(
            instance.workspace_id
        )
        return AgentHandler().get_configuration(
            instance, provider_state=provider_state
        )["readiness"]


class AgentConfigurationSerializer(serializers.Serializer):
    # Settings readers need readiness from the same snapshot as the editable values,
    # including after PATCH. Application payloads expose readiness to all readers.
    readiness = serializers.ChoiceField(choices=READINESS_CHOICES)
    instructions = serializers.CharField(allow_blank=True, trim_whitespace=False)
    provider_type = serializers.CharField(allow_null=True)
    model_identifier = serializers.CharField(allow_null=True)
    errors = serializers.DictField(
        child=serializers.ChoiceField(choices=["required", "unavailable"])
    )


class AgentConfigurationUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = AgentApplication
        fields = ("instructions", "provider_type", "model_identifier")
        extra_kwargs = {
            "instructions": {
                "max_length": AGENT_TEXT_MAX_LENGTH,
                "trim_whitespace": False,
            },
        }


class AgentConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConversation
        fields = ("id", "uuid", "title", "created_on", "updated_on")


class AgentMessageAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="first_name")


class AgentTurnStateSerializer(serializers.ModelSerializer):
    run_id = serializers.SerializerMethodField(
        help_text="The run still answering this turn, to follow its output."
    )

    class Meta:
        model = AgentTurn
        fields = ("id", "status", "error_code", "run_id")

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_run_id(self, turn: AgentTurn) -> UUID | None:
        return self.context.get("active_runs", {}).get(turn.id)


class AgentMessageSerializer(serializers.ModelSerializer):
    author = AgentMessageAuthorSerializer(
        source="author_user", allow_null=True, read_only=True
    )
    turn = AgentTurnStateSerializer(allow_null=True, read_only=True)

    class Meta:
        model = AgentMessage
        fields = ("id", "uuid", "role", "content", "created_on", "author", "turn")
        read_only_fields = ("id",)



class AgentMessageContentSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    content = serializers.CharField(
        max_length=AGENT_TEXT_MAX_LENGTH, trim_whitespace=False
    )

    def validate_content(self, value: str) -> str:
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
