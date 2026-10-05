from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.user_files.serializers import UserFileField
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentChatToolApproval,
    AgentDefinition,
    AgentSkill,
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
    type = serializers.CharField()
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
    type = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    enabled = serializers.BooleanField(required=False)


class UpdateAgentChatChannelSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    config = serializers.DictField(required=False)
    enabled = serializers.BooleanField(required=False)
