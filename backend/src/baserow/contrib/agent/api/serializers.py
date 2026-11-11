from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.pagination import KeysetCursorField, PageNumberPagination
from baserow.contrib.agent.constants import (
    RUN_AS_SUBJECT_TYPES,
    AgentConfigurationErrorCode,
    AgentReadinessState,
    AgentRunAsState,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentToolApproval,
)
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.types import AgentConfiguration, AgentConversationCursor
from baserow.contrib.agent.validators import (
    AGENT_REJECTION_REASON_MAX_LENGTH,
    AGENT_TEXT_MAX_LENGTH,
)
from baserow.core.chat_runs.constants import ChatRunStepStatus
from baserow.core.generative_ai.constants import ReasoningEffort
from baserow.core.tools.errors import ToolErrorCode

READINESS_CHOICES = [state.value for state in AgentReadinessState]
REASONING_EFFORT_CHOICES = [effort.value for effort in ReasoningEffort]


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
        readiness, _ = AgentHandler().get_configuration_readiness(
            instance, provider_state=provider_state
        )
        return readiness


class AgentRunAsSerializer(serializers.Serializer):
    type = serializers.CharField(allow_null=True)
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    trashed = serializers.BooleanField()
    status = serializers.ChoiceField(
        choices=[
            state.value for state in AgentRunAsState if state != AgentRunAsState.UNSET
        ]
    )


class AgentRunAsSubjectsQueryParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    size = serializers.IntegerField(min_value=1, max_value=100, required=False)
    search = serializers.CharField(required=False, allow_blank=True, default="")


class AgentToolSerializer(serializers.Serializer):
    name = serializers.CharField()
    group = serializers.CharField()
    changes_data = serializers.BooleanField()


class AgentConfigurationSerializer(serializers.Serializer):
    # Settings readers need readiness from the same snapshot as the editable values,
    # including after PATCH. Application payloads expose readiness to all readers.
    readiness = serializers.ChoiceField(choices=READINESS_CHOICES)
    instructions = serializers.CharField(allow_blank=True, trim_whitespace=False)
    provider_type = serializers.CharField(allow_null=True)
    model_identifier = serializers.CharField(allow_null=True)
    reasoning_effort = serializers.ChoiceField(
        choices=REASONING_EFFORT_CHOICES,
        allow_null=True,
        help_text="How much the model reasons before it replies. Null uses the "
        "model's default.",
    )
    applied_reasoning_effort = serializers.ChoiceField(
        choices=REASONING_EFFORT_CHOICES,
        allow_null=True,
        help_text="The reasoning effort replies use with the selected model: the "
        "chosen one, or the next higher one the model accepts. Null means replies "
        "use the model's default, because none is chosen, the model doesn't accept "
        "one, or the model isn't available.",
    )
    run_as = serializers.SerializerMethodField(
        help_text="The configured identity and its active, trashed or missing status. "
        "Null means no workspace access was selected."
    )
    allowed_tools = serializers.ListField(
        child=serializers.CharField(),
        help_text="The names of the tools the agent may call while it has an "
        "identity to act as.",
    )
    ask_first_tools = serializers.ListField(
        child=serializers.CharField(),
        help_text="The names of the allowed tools that wait for the conversation "
        "owner's approval before they run.",
    )
    available_tools = serializers.SerializerMethodField(
        help_text="Every tool an agent can be allowed to call, with its group and "
        "whether it changes data."
    )
    web_search_enabled = serializers.BooleanField(
        help_text="Whether the agent may search the web through its AI provider."
    )
    web_search_available = serializers.BooleanField(
        help_text="Whether the agent's model may try to search the web. Its provider "
        "can still refuse a search, which the reply then shows."
    )
    web_search_blocked_by_tools = serializers.BooleanField(
        help_text="Whether the agent's model can search the web, but not while the "
        "agent uses workspace tools."
    )
    errors = serializers.DictField(
        child=serializers.ChoiceField(
            choices=[error.value for error in AgentConfigurationErrorCode]
        )
    )

    @extend_schema_field(AgentToolSerializer(many=True))
    def get_available_tools(self, configuration: AgentConfiguration) -> list[dict]:
        """
        List the registered tools.

        :param configuration: The configuration being serialized.
        :return: Each tool's name, group and whether it changes data.
        """

        return [
            {
                "name": tool_type.type,
                "group": tool_type.group,
                "changes_data": tool_type.changes_data,
            }
            for tool_type in agent_tool_type_registry.get_all()
        ]

    @extend_schema_field(AgentRunAsSerializer(allow_null=True))
    def get_run_as(self, configuration: AgentConfiguration) -> dict | None:
        """
        Serialize the identity from the configuration's resolved snapshot.

        :param configuration: The configuration being serialized.
        :return: The configured identity and status, or None when unset.
        """

        run_as = configuration.run_as
        if run_as.status == AgentRunAsState.UNSET:
            return None
        return {
            "type": run_as.subject_type,
            "id": run_as.subject_id,
            "name": run_as.name,
            "trashed": run_as.status == AgentRunAsState.TRASHED,
            "status": run_as.status.value,
        }


class AgentConfigurationUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.ModelSerializer
):
    reasoning_effort = serializers.ChoiceField(
        choices=REASONING_EFFORT_CHOICES,
        allow_null=True,
        required=False,
        help_text="How much the model reasons before it replies. Null uses the "
        "model's default. A model that doesn't accept it uses the next higher "
        "effort it accepts, or its default.",
    )
    run_as_subject_type = serializers.ChoiceField(
        choices=RUN_AS_SUBJECT_TYPES,
        allow_null=True,
        required=False,
        help_text="The type of the identity the agent's tools act as. Provide it "
        "with run_as_subject_id; both null means no workspace access and clears "
        "the allowed tools.",
    )
    run_as_subject_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="The id of the identity the agent's tools act as.",
    )
    allowed_tools = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="The names of all the tools the agent may call. Tools left out "
        "are turned off. Without a selected Run as identity, all tools stay off.",
    )
    ask_first_tools = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="The names of the allowed tools that wait for the conversation "
        "owner's approval. Provide it with allowed_tools. When it's left out, newly "
        "allowed tools that change data ask first and the other tools keep their "
        "setting.",
    )

    class Meta:
        model = AgentApplication
        fields = (
            "instructions",
            "provider_type",
            "model_identifier",
            "reasoning_effort",
            "run_as_subject_type",
            "run_as_subject_id",
            "allowed_tools",
            "web_search_enabled",
            "ask_first_tools",
        )
        extra_kwargs = {
            "instructions": {
                "max_length": AGENT_TEXT_MAX_LENGTH,
                "trim_whitespace": False,
            },
        }

    def validate_allowed_tools(self, names: list[str]) -> list[str]:
        """
        Accept only registered tools.

        :param names: The requested tool names.
        :raises ValidationError: When a name isn't a tool.
        :return: The names without duplicates.
        """

        unknown = set(names) - set(agent_tool_type_registry.get_types())
        if unknown:
            raise serializers.ValidationError(
                f"Unknown tools: {', '.join(sorted(unknown))}."
            )
        return list(dict.fromkeys(names))

    validate_ask_first_tools = validate_allowed_tools

    def validate(self, values: dict) -> dict:
        """
        Require the run-as type and id together, both set or both null, and the
        tools that ask first to be among the allowed tools given with them.

        :param values: The validated fields.
        :raises ValidationError: When only one of the run-as fields is given or
            set, or a tool that asks first isn't allowed.
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
        if "ask_first_tools" in values:
            if "allowed_tools" not in values:
                raise serializers.ValidationError(
                    {"ask_first_tools": "Provide allowed_tools with ask_first_tools."}
                )
            not_allowed = set(values["ask_first_tools"]) - set(values["allowed_tools"])
            if not_allowed:
                raise serializers.ValidationError(
                    {
                        "ask_first_tools": "Tools that ask first must be allowed: "
                        f"{', '.join(sorted(not_allowed))}."
                    }
                )
        return values


class AgentConversationSerializer(serializers.ModelSerializer):
    run_id = serializers.SerializerMethodField(
        help_text="The run writing a reply in this conversation, or null."
    )
    pending_approval_count = serializers.SerializerMethodField(
        help_text="The number of held tool calls in this conversation waiting for "
        "the owner's decision."
    )

    class Meta:
        model = AgentConversation
        fields = (
            "id",
            "uuid",
            "title",
            "created_on",
            "updated_on",
            "run_id",
            "pending_approval_count",
            "pinned",
        )

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_run_id(self, conversation: AgentConversation) -> UUID | None:
        return self.context.get("conversation_runs", {}).get(conversation.id)

    @extend_schema_field(serializers.IntegerField())
    def get_pending_approval_count(self, conversation: AgentConversation) -> int:
        return self.context.get("conversation_pending_approvals", {}).get(
            conversation.id, 0
        )


class AgentConversationUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    pinned = serializers.BooleanField(required=False)
    title = serializers.CharField(
        required=False,
        max_length=AgentConversation._meta.get_field("title").max_length,
    )


class AgentMessageStepItemErrorSerializer(serializers.Serializer):
    item = serializers.JSONField(help_text="The failed item's name or ID.")
    code = serializers.ChoiceField(choices=list(ToolErrorCode))
    message = serializers.CharField()


class AgentMessageStepSerializer(serializers.Serializer):
    id = serializers.CharField()
    tool = serializers.CharField()
    status = serializers.ChoiceField(choices=list(ChatRunStepStatus))
    error_code = serializers.ChoiceField(choices=list(ToolErrorCode), required=False)
    error_message = serializers.CharField(required=False)
    item_errors = AgentMessageStepItemErrorSerializer(many=True, required=False)
    changes_data = serializers.BooleanField()
    input = serializers.DictField()
    facts = serializers.DictField()


class AgentToolApprovalSerializer(serializers.ModelSerializer):
    tool = serializers.CharField(source="tool_name")

    class Meta:
        model = AgentToolApproval
        fields = ("id", "step_id", "pause", "tool", "status", "reason")


class AgentMessageSerializer(serializers.ModelSerializer):
    steps = AgentMessageStepSerializer(many=True, allow_null=True, read_only=True)
    approvals = AgentToolApprovalSerializer(
        many=True,
        read_only=True,
        help_text="The reply's held tool calls, joined to their steps by step_id, "
        "with the owner's decision on each.",
    )
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
            "steps",
            "approvals",
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


class AgentToolDecisionSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    id = serializers.IntegerField(help_text="The id of a pending approval.")
    approved = serializers.BooleanField(
        help_text="Whether the held call may run. A rejected call never runs."
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=AGENT_REJECTION_REASON_MAX_LENGTH,
        help_text="Why the call is rejected, passed on to the agent. Only accepted "
        "with a rejection.",
    )

    def validate(self, values: dict) -> dict:
        """
        Accept a reason only for a rejection.

        :param values: The validated fields.
        :raises ValidationError: When an approval has a reason.
        :return: The validated fields.
        """

        values = super().validate(values)
        if values["approved"] and "reason" in values:
            raise serializers.ValidationError(
                {"reason": "Only a rejection has a reason."}
            )
        return values


class AgentToolDecisionsSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    decisions = AgentToolDecisionSerializer(
        many=True,
        allow_empty=False,
        help_text="Decisions on pending approvals of the waiting reply, at most one "
        "per approval. The reply continues once none is pending.",
    )
    always_allow = serializers.BooleanField(
        default=False,
        help_text="Whether the tools of the approved calls stop asking first. Needs "
        "the permissions to update the agent's configuration.",
    )

    def validate_decisions(self, decisions: list[dict]) -> list[dict]:
        """
        Accept one decision per approval.

        :param decisions: The validated decisions.
        :raises ValidationError: When an approval is decided twice.
        :return: The decisions.
        """

        ids = [decision["id"] for decision in decisions]
        if len(set(ids)) < len(ids):
            raise serializers.ValidationError("Decide each approval once.")
        return decisions


class AgentMessageCreatedSerializer(serializers.Serializer):
    conversation = AgentConversationSerializer()
    message = AgentMessageSerializer()
    reply = AgentMessageSerializer(allow_null=True)


class AgentConversationCursorField(KeysetCursorField):
    def to_internal_value(self, data) -> AgentConversationCursor:
        value = serializers.CharField.to_internal_value(self, data)
        pinned, separator, position = value.partition(":")
        if separator and pinned not in ("0", "1"):
            raise serializers.ValidationError("Invalid cursor.")
        cursor = super().to_internal_value(position if separator else value)
        return AgentConversationCursor(
            value=cursor.value, id=cursor.id, pinned=separator != "" and pinned == "1"
        )


class AgentConversationsQuerySerializer(serializers.Serializer):
    pinned = serializers.BooleanField(required=False)
    has_pending_approvals = serializers.BooleanField(required=False)
    limit = serializers.IntegerField(
        default=20,
        min_value=1,
        max_value=100,
        help_text="Maximum number of conversations to return.",
    )
    cursor = AgentConversationCursorField(
        required=False,
        help_text="The `next_cursor` of the previous page, omitted for the first page.",
    )


class AgentConversationsResponseSerializer(serializers.Serializer):
    results = AgentConversationSerializer(many=True)
    next_cursor = serializers.CharField(
        allow_null=True,
        help_text="Pass as `cursor` to get the next page, `null` when no more "
        "conversations follow.",
    )


class AgentMessagePagination(PageNumberPagination):
    page_size = 50
