from django.conf import settings
from django.db import models
from django.db.models import Q

from baserow.core.mixins import (
    BigAutoFieldMixin,
    CreatedAndUpdatedOnMixin,
    TrashableModelMixin,
)
from baserow.core.models import Application


class AgentApplication(Application):
    """A single reusable agent, owned and managed as a workspace application."""

    instructions = models.TextField(blank=True, default="", db_default="")
    provider_type = models.CharField(
        max_length=255, null=True, blank=True, db_default=None
    )
    model_identifier = models.CharField(
        max_length=255, null=True, blank=True, db_default=None
    )
    # Empty uses the model's default; models without reasoning ignore it.
    reasoning_effort = models.CharField(
        max_length=32, null=True, blank=True, db_default=None
    )
    # The subject the Agent's tools act as; empty means no workspace access.
    run_as_subject_type = models.CharField(
        max_length=255, null=True, blank=True, db_default=None
    )
    run_as_subject_id = models.BigIntegerField(null=True, blank=True, db_default=None)
    # Searches run at the AI provider, which charges for them.
    web_search_enabled = models.BooleanField(default=False, db_default=False)


class AgentAllowedTool(models.Model):
    """A tool an Agent may call. A missing row means the tool is not allowed."""

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="allowed_tools"
    )
    name = models.CharField(max_length=100)
    ask_first = models.BooleanField(default=False, db_default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "name"], name="agent_allowed_tool_unique_name"
            )
        ]


class AgentConversation(
    TrashableModelMixin, BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model
):
    """A conversation with an agent, private to the user who started it."""

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="conversations"
    )
    uuid = models.UUIDField(unique=True)
    title = models.CharField(max_length=250)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    # Reads are already narrowed to one owner's conversations by the index below.
    trashed = models.BooleanField(default=False, db_default=False)
    pinned = models.BooleanField(default=False, db_default=False)

    class Meta:
        ordering = ("-pinned", "-updated_on", "-id")
        indexes = [
            models.Index(
                fields=["agent", "owner_user", "-updated_on", "-id"],
                name="agent_conversation_owner_idx",
            ),
            models.Index(
                fields=["agent", "owner_user", "-pinned", "-updated_on", "-id"],
                name="agent_conversation_pinned_idx",
            ),
        ]


class AgentReplyStatus(models.TextChoices):
    """A reply's status: its run's status, or waiting while held calls are decided."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    WAITING = "waiting"


class AgentMessage(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """A message as shown in a conversation, not as sent to the AI model."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name="messages"
    )
    uuid = models.UUIDField()
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.USER, db_default=Role.USER
    )
    content = models.TextField()
    # Only the agent's replies have one.
    status = models.CharField(
        max_length=16, choices=AgentReplyStatus.choices, null=True
    )
    error_code = models.CharField(max_length=64, blank=True, default="", db_default="")
    steps = models.JSONField(null=True)

    class Meta:
        ordering = ("-id",)
        indexes = [
            models.Index(
                fields=["conversation", "-id"], name="agent_message_history_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "uuid"], name="unique_agent_message_uuid"
            ),
        ]


class AgentToolApproval(BigAutoFieldMixin, models.Model):
    """A held tool call of a reply, waiting for or decided by the owner."""

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    # The unique step and the pending index both lead with the reply.
    reply = models.ForeignKey(
        AgentMessage,
        on_delete=models.CASCADE,
        related_name="approvals",
        db_index=False,
    )
    tool_call_id = models.CharField(max_length=255)
    step_id = models.CharField(max_length=64)
    pause = models.PositiveSmallIntegerField(
        help_text="Which pause of its reply held the call, counting from 1."
    )
    tool_name = models.CharField(max_length=100)
    tool_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_default="",
        help_text="For an MCP tool, its server, account and definition when the "
        "call was held. An approved call only runs while they're the same.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_default=Status.PENDING,
    )
    reason = models.TextField(blank=True, default="", db_default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_on = models.DateTimeField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            # Not tool_call_id: providers may reuse it across responses.
            models.UniqueConstraint(
                fields=["reply", "step_id"], name="agent_tool_approval_unique_step"
            ),
        ]
        indexes = [
            models.Index(
                fields=["reply"],
                condition=Q(status="pending"),
                name="agent_approval_pending_idx",
            ),
        ]


class AgentReplyTranscript(BigAutoFieldMixin, models.Model):
    """The model, new messages and usage of one reply, for diagnostics and resuming."""

    reply = models.OneToOneField(
        AgentMessage, on_delete=models.CASCADE, related_name="transcript"
    )
    provider_type = models.CharField(max_length=255, null=True, blank=True)
    model_identifier = models.CharField(max_length=255, null=True, blank=True)
    # Kept as pydantic-ai dumped them, so they load back into its message types.
    model_messages = models.JSONField(null=True)
    usage = models.JSONField(null=True)
    # The whole run, not only its new messages, so a resume keeps its request limit.
    paused_conversation = models.JSONField(null=True)
    # A provider that refused web search would refuse the resume too.
    paused_web_search = models.BooleanField(default=False, db_default=False)
    # Held calls were named and approved as this identity, so they never run as another.
    paused_run_as_subject_type = models.CharField(max_length=255, null=True)
    paused_run_as_subject_id = models.BigIntegerField(null=True)

    def paused_as(self, subject_type: str | None, subject_id: int | None) -> bool:
        """
        :param subject_type: An identity's subject type, or None.
        :param subject_id: An identity's subject id, or None.
        :return: Whether the paused run acted as that identity.
        """

        return (self.paused_run_as_subject_type, self.paused_run_as_subject_id) == (
            subject_type,
            subject_id,
        )
