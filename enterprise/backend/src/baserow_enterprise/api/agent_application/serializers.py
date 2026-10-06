from django.conf import settings
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from loguru import logger
from rest_framework import serializers

from baserow.api.services.serializers import (
    PolymorphicServiceSerializer,
    ServiceSerializer,
)
from baserow.api.user_files.serializers import UserFileField
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.agent_application.channels.registries import (
    agent_chat_channel_type_registry,
)
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentChatToolApproval,
    AgentDefinition,
    AgentSkill,
)
from baserow_enterprise.agent_application.tools.registries import (
    agent_tool_type_registry,
)
from baserow_enterprise.agent_application.triggers.registries import (
    agent_trigger_type_registry,
)


class AgentSkillSerializer(serializers.ModelSerializer):
    skill_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="skill.name", read_only=True)
    description = serializers.CharField(source="skill.description", read_only=True)

    class Meta:
        model = AgentSkill
        fields = ("id", "skill_id", "name", "description", "mode", "order")
        read_only_fields = fields


class AgentDefinitionSerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()

    class Meta:
        model = AgentDefinition
        fields = (
            "id",
            "application_id",
            "name",
            "description",
            "instructions",
            "memory",
            "ai_generative_ai_type",
            "ai_generative_ai_model",
            "ai_temperature",
            "skills",
            "created_on",
            "updated_on",
        )
        read_only_fields = ("id", "application_id", "created_on", "updated_on")

    @extend_schema_field(AgentSkillSerializer(many=True))
    def get_skills(self, agent):
        return AgentSkillSerializer(
            agent.agent_skills.select_related("skill").order_by("order", "id"),
            many=True,
        ).data


class SetAgentSkillSerializer(serializers.Serializer):
    skill_id = serializers.IntegerField()
    mode = serializers.ChoiceField(
        choices=AgentSkill.Mode.choices, default=AgentSkill.Mode.ALWAYS
    )


class UpdateAgentDefinitionSerializer(serializers.ModelSerializer):
    skills = SetAgentSkillSerializer(
        many=True,
        required=False,
        help_text="Replaces the workspace skills the agent follows, in order.",
    )

    class Meta:
        model = AgentDefinition
        fields = (
            "name",
            "description",
            "instructions",
            "memory",
            "ai_generative_ai_type",
            "ai_generative_ai_model",
            "ai_temperature",
            "skills",
        )
        extra_kwargs = {field: {"required": False} for field in fields}


class DraftAgentInstructionsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=4000)


class ImproveAgentInstructionsSerializer(serializers.Serializer):
    instructions = serializers.CharField(max_length=20000)


class AgentInstructionsSerializer(serializers.Serializer):
    instructions = serializers.CharField()


class UpdateAgentChatSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=False, allow_blank=True, max_length=AgentChat.TITLE_MAX_LENGTH
    )
    pinned = serializers.BooleanField(required=False)


class SendAgentChatMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=65536)
    user_files = serializers.ListField(
        child=UserFileField(),
        required=False,
        max_length=10,
        help_text=(
            "Previously uploaded user files to attach to the message; they "
            "are injected into the model prompt of this turn."
        ),
    )


class CreateAgentTriggerSerializer(serializers.Serializer):
    service_type = serializers.CharField()
    enabled = serializers.BooleanField(required=False)
    service = serializers.DictField(required=False)


class UpdateAgentTriggerSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    service = serializers.DictField(required=False)


class CreateAgentToolSerializer(serializers.Serializer):
    # Checked against the registry so an unknown type is a validation error
    # instead of an unmapped registry exception.
    type = serializers.ChoiceField(
        choices=lazy(agent_tool_type_registry.get_types, list)()
    )
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    service_type = serializers.CharField(required=False)
    service = serializers.DictField(required=False)


class UpdateAgentToolSerializer(serializers.Serializer):
    identity_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            "The workspace agent this tool acts as, or null for the application's "
            "identity."
        ),
    )
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    service = serializers.DictField(required=False)


class AgentChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentChat
        fields = (
            "id",
            "uuid",
            "agent_id",
            "user_id",
            "title",
            "pinned",
            "status",
            "source",
            "trigger_type",
            "started_on",
            "completed_on",
            "error",
            "total_input_tokens",
            "total_output_tokens",
            "created_on",
            "updated_on",
        )
        read_only_fields = fields


class AgentChatWithPayloadSerializer(AgentChatSerializer):
    """
    The transcript endpoint additionally returns the trigger payload the
    conversation started with; it can be large, so the list and the realtime
    updates leave it out.
    """

    class Meta(AgentChatSerializer.Meta):
        fields = (*AgentChatSerializer.Meta.fields, "event_payload")
        read_only_fields = fields


class AgentChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentChatMessage
        fields = (
            "id",
            "chat_id",
            "role",
            "content",
            "artifacts",
            "attachments",
            "input_tokens",
            "output_tokens",
            "created_on",
        )
        read_only_fields = fields


class AgentChatToolApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentChatToolApproval
        fields = (
            "id",
            "chat_id",
            "message_id",
            "tool_call_id",
            "tool_name",
            "tool_args",
            "preview",
            "status",
            "reason",
            "decided_by_id",
            "decided_at",
            "created_on",
        )
        read_only_fields = fields


class AgentApplicationToolApprovalSerializer(AgentChatToolApprovalSerializer):
    """
    Approval with its conversation context, for the application-wide pending
    approvals overview.
    """

    chat_uuid = serializers.UUIDField(source="chat.uuid", read_only=True)
    chat_title = serializers.CharField(source="chat.title", read_only=True)

    class Meta(AgentChatToolApprovalSerializer.Meta):
        fields = AgentChatToolApprovalSerializer.Meta.fields + (
            "chat_uuid",
            "chat_title",
        )
        read_only_fields = fields


class AgentChatTranscriptSerializer(serializers.Serializer):
    chat = AgentChatWithPayloadSerializer()
    messages = AgentChatMessageSerializer(many=True)
    tool_approvals = AgentChatToolApprovalSerializer(many=True)


class AgentChatRunStartedSerializer(AgentChatSerializer):
    prompt_message_id = serializers.SerializerMethodField(
        help_text="The human message this run answers; streaming events of the "
        "run refer to it."
    )

    class Meta(AgentChatSerializer.Meta):
        fields = (*AgentChatSerializer.Meta.fields, "prompt_message_id")
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.INT)
    def get_prompt_message_id(self, chat):
        return self.context["prompt_message"].id


class AgentUsageSerializer(serializers.Serializer):
    total_input_tokens = serializers.IntegerField()
    total_output_tokens = serializers.IntegerField()
    chat_count = serializers.IntegerField()


class AgentToolApprovalDecisionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    approved = serializers.BooleanField()
    reason = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2000
    )
    dont_ask_again = serializers.BooleanField(
        required=False,
        default=False,
        help_text="When approving, also let this tool run without approval "
        "from now on.",
    )


class DecideAgentToolApprovalsSerializer(serializers.Serializer):
    decisions = AgentToolApprovalDecisionSerializer(many=True)


class CreateAgentChatChannelSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=lazy(agent_chat_channel_type_registry.get_types, list)()
    )
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    enabled = serializers.BooleanField(required=False)


class UpdateAgentChatChannelSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    enabled = serializers.BooleanField(required=False)


class AgentTriggerTokenSerializer(serializers.Serializer):
    token = serializers.CharField(
        help_text="A `{{trigger.…}}` placeholder the instructions may use."
    )
    description = serializers.CharField()


class AgentTriggerSerializer(serializers.Serializer):
    """
    Read-only. Expects `trigger.service` to be the specific service, which the
    list view loads in bulk; `.specific` is then a no-op instead of a query
    per trigger.
    """

    id = serializers.IntegerField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    service_type = serializers.CharField(
        read_only=True, help_text="The type of the trigger service."
    )
    service = PolymorphicServiceSerializer(
        read_only=True, help_text="The trigger service with its configuration."
    )
    tokens = AgentTriggerTokenSerializer(many=True, read_only=True)
    sample_payload = serializers.DictField(
        read_only=True,
        allow_null=True,
        help_text="An example of the event payload this trigger starts a "
        "conversation with; also what 'run once' hands the agent.",
    )

    def to_representation(self, trigger):
        service = trigger.service.specific
        service_type = service.get_type().type
        tokens = []
        sample_payload = None
        try:
            trigger_type = agent_trigger_type_registry.get_by_service_type(service_type)
            tokens = trigger_type.get_tokens(trigger)
            sample_payload = trigger_type.get_sample_payload(trigger)
        except Exception:
            # The example is a convenience; a trigger must still list without it.
            logger.exception("Failed to build the trigger example for {}", trigger.id)
        return {
            "id": trigger.id,
            "enabled": trigger.enabled,
            "service_type": service_type,
            "service": service_type_registry.get_serializer(
                service, ServiceSerializer
            ).data,
            "tokens": tokens,
            "sample_payload": sample_payload,
        }


class AgentToolSerializer(serializers.Serializer):
    """
    Read-only. Like `AgentTriggerSerializer`, it expects `tool.service` to be
    the specific service when the tool has one.
    """

    id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True, help_text="The agent tool type.")
    name = serializers.CharField(read_only=True)
    config = serializers.DictField(
        read_only=True,
        help_text="The type-specific configuration; secrets are masked.",
    )
    order = serializers.IntegerField(read_only=True)
    identity_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
        help_text="The workspace agent this tool acts as, or null for the "
        "application's identity.",
    )
    service_type = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text="Set for service-backed tools only.",
    )
    service = PolymorphicServiceSerializer(
        read_only=True,
        allow_null=True,
        help_text="The dispatched service of a service-backed tool.",
    )

    def to_representation(self, tool):
        service_data = None
        service_type = None
        if tool.service_id is not None:
            service = tool.service.specific
            service_type = service.get_type().type
            service_data = service_type_registry.get_serializer(
                service, ServiceSerializer
            ).data
        return {
            "id": tool.id,
            "type": tool.type,
            "name": tool.name,
            "config": agent_tool_type_registry.get(tool.type).get_public_config(tool),
            "order": tool.order,
            "identity_id": tool.identity_id,
            "service_type": service_type,
            "service": service_data,
        }


class AgentChatChannelSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True, help_text="The chat channel type.")
    name = serializers.CharField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    config = serializers.DictField(
        read_only=True,
        help_text="The type-specific configuration; secrets are masked.",
    )
    events_url = serializers.URLField(
        read_only=True,
        help_text="The inbound webhook URL the external service posts events to.",
    )
    manifest = serializers.DictField(
        read_only=True,
        allow_null=True,
        help_text="A ready-made app definition for the external service, when "
        "it supports one.",
    )

    def to_representation(self, channel):
        channel_type = agent_chat_channel_type_registry.get(channel.type)
        events_url = (
            f"{settings.PUBLIC_BACKEND_URL}/api/agent_application/channels/"
            f"{channel.uid}/events/"
        )
        return {
            "id": channel.id,
            "type": channel.type,
            "name": channel.name,
            "enabled": channel.enabled,
            "config": channel_type.get_public_config(channel),
            "events_url": events_url,
            "manifest": channel_type.get_manifest(channel, events_url),
        }


class AgentWorkspaceToolSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="The tool name to grant in the config.")
    group = serializers.CharField()
    group_label = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    is_write = serializers.BooleanField(help_text="Whether the tool changes data.")
