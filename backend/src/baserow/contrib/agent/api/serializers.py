from typing import get_args
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.pagination import PageNumberPagination
from baserow.contrib.agent.constants import RUN_AS_SUBJECT_TYPES
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
)
from baserow.contrib.agent.types import AgentConfiguration, AgentReadinessState
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH
from baserow.core.registries import subject_type_registry

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


class AgentRunAsSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=RUN_AS_SUBJECT_TYPES)
    id = serializers.IntegerField()
    name = serializers.CharField()
    trashed = serializers.BooleanField()


class AgentConfigurationSerializer(serializers.Serializer):
    # Settings readers need readiness from the same snapshot as the editable values,
    # including after PATCH. Application payloads expose readiness to all readers.
    readiness = serializers.ChoiceField(choices=READINESS_CHOICES)
    instructions = serializers.CharField(allow_blank=True, trim_whitespace=False)
    provider_type = serializers.CharField(allow_null=True)
    model_identifier = serializers.CharField(allow_null=True)
    run_as = serializers.SerializerMethodField(
        help_text="The identity the agent's tools act as, or null for no workspace "
        "access. A trashed identity is included so it can be reported."
    )
    errors = serializers.DictField(
        child=serializers.ChoiceField(choices=["required", "unavailable"])
    )

    @extend_schema_field(AgentRunAsSerializer(allow_null=True))
    def get_run_as(self, configuration: AgentConfiguration) -> dict | None:
        """
        Describe the identity to run as, if it still exists.

        :param configuration: The configuration being serialized.
        :return: The identity with its type, or None.
        """

        subject_type = configuration["run_as_subject_type"]
        subject = AgentHandler().get_run_as_subject(
            subject_type, configuration["run_as_subject_id"], include_trash=True
        )
        if subject is None:
            return None
        return {
            **subject_type_registry.get_serializer(subject).data,
            "type": subject_type,
        }


class AgentConfigurationUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.ModelSerializer
):
    run_as_subject_type = serializers.ChoiceField(
        choices=RUN_AS_SUBJECT_TYPES,
        allow_null=True,
        required=False,
        help_text="The type of the identity the agent's tools act as. Provide it "
        "with run_as_subject_id; both null means no workspace access.",
    )
    run_as_subject_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="The id of the identity the agent's tools act as.",
    )

    class Meta:
        model = AgentApplication
        fields = (
            "instructions",
            "provider_type",
            "model_identifier",
            "run_as_subject_type",
            "run_as_subject_id",
        )
        extra_kwargs = {
            "instructions": {
                "max_length": AGENT_TEXT_MAX_LENGTH,
                "trim_whitespace": False,
            },
        }

    def validate(self, values: dict) -> dict:
        """
        Require the run-as type and id together, both set or both null.

        :param values: The validated fields.
        :raises ValidationError: When only one of them is given or set.
        :return: The validated fields.
        """

        values = super().validate(values)
        fields = AgentHandler.run_as_fields
        given = [field for field in fields if field in values]
        if given and (
            len(given) < len(fields)
            or len({values[field] is None for field in fields}) > 1
        ):
            raise serializers.ValidationError(
                "run_as_subject_type and run_as_subject_id must be set together."
            )
        return values


class AgentConversationSerializer(serializers.ModelSerializer):
    run_id = serializers.SerializerMethodField(
        help_text="The run writing a reply in this conversation, or null."
    )

    class Meta:
        model = AgentConversation
        fields = ("id", "uuid", "title", "created_on", "updated_on", "run_id")

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_run_id(self, conversation: AgentConversation) -> UUID | None:
        return self.context.get("conversation_runs", {}).get(conversation.id)


class AgentMessageSerializer(serializers.ModelSerializer):
    run_id = serializers.SerializerMethodField(
        help_text=(
            "The run writing this reply, to follow its output: set while it runs "
            "and in the response that started it."
        )
    )

    class Meta:
        model = AgentMessage
        fields = (
            "id",
            "uuid",
            "role",
            "content",
            "created_on",
            "status",
            "error_code",
            "run_id",
        )
        read_only_fields = ("id",)

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_run_id(self, message: AgentMessage) -> UUID | None:
        return self.context.get("active_runs", {}).get(message.id)


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
    reply = AgentMessageSerializer(allow_null=True)


class AgentConversationPagination(PageNumberPagination):
    page_size = 20


class AgentMessagePagination(PageNumberPagination):
    page_size = 50
