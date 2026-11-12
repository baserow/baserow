from django.conf import settings
from django.db import models
from django.db.models import Q

from baserow.contrib.agent.constants import (
    AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
    AGENT_TRIGGER_NAME_MAX_LENGTH,
)
from baserow.core.formula.field import FormulaField
from baserow.core.mixins import (
    BigAutoFieldMixin,
    CreatedAndUpdatedOnMixin,
    TrashableModelMixin,
)
from baserow.core.models import Application
from baserow.core.services.models import Service


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


class AgentAction(TrashableModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    """One named tool backed by its own configured integration service."""

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="actions"
    )
    service = models.OneToOneField(
        Service, on_delete=models.CASCADE, related_name="agent_action"
    )
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    inputs = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True, db_default=True)
    ask_first = models.BooleanField(default=False, db_default=False)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "name"],
                condition=Q(trashed=False),
                name="agent_action_unique_live_name",
            )
        ]


class AgentTrigger(TrashableModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    """An agent-owned trigger service whose events start shared conversations."""

    class OnOverlap(models.TextChoices):
        """What a firing does while one of the trigger's replies is still going."""

        SKIP = "skip", "Skip"
        WAIT = "wait", "Wait for the previous run"
        PARALLEL = "parallel", "Run in parallel"

    class SkipReason(models.TextChoices):
        """Why the trigger's last skipped firing started nothing."""

        RATE_LIMITED = "rate_limited", "Rate limited"
        AGENT_RATE_LIMITED = "agent_rate_limited", "Agent rate limited"
        PREVIOUS_RUNNING = "previous_running", "Previous run still going"
        QUEUE_FULL = "queue_full", "Queue full"
        NO_ACCESS = "no_access", "No access"
        EVENT_TOO_LARGE = "event_too_large", "Event too large"

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="triggers"
    )
    service = models.OneToOneField(
        Service, on_delete=models.CASCADE, related_name="agent_trigger"
    )
    # Blank shows a default worded by the trigger's service type.
    name = models.CharField(
        max_length=AGENT_TRIGGER_NAME_MAX_LENGTH, blank=True, default="", db_default=""
    )
    enabled = models.BooleanField(default=True, db_default=True)
    message = FormulaField(default="", db_default="", blank=True)
    on_overlap = models.CharField(
        max_length=16,
        choices=OnOverlap.choices,
        default=OnOverlap.SKIP,
        db_default=OnOverlap.SKIP,
    )
    # Records of a list payload one conversation receives; other payloads ignore it.
    batch_size = models.PositiveSmallIntegerField(
        default=AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
        db_default=AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
    )
    # A skip is shown while it is newer than the last accepted firing.
    last_fired_on = models.DateTimeField(null=True, blank=True)
    last_skipped_on = models.DateTimeField(null=True, blank=True)
    last_skipped_reason = models.CharField(
        max_length=32,
        choices=SkipReason.choices,
        blank=True,
        default="",
        db_default="",
    )

    class Meta:
        ordering = ("id",)


class AgentConversation(
    TrashableModelMixin, BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model
):
    """
    A conversation with an agent: private to the user who started it, or shared
    (no owner) when a trigger started it.
    """

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="conversations"
    )
    uuid = models.UUIDField(unique=True)
    title = models.CharField(max_length=250)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    trigger = models.ForeignKey(
        AgentTrigger,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    # The list indexes lead with the agent, so reads never need one on trashed.
    trashed = models.BooleanField(default=False, db_default=False)
    pinned = models.BooleanField(default=False, db_default=False)

    @property
    def is_shared(self) -> bool:
        """
        :return: Whether a trigger started the conversation: it has no owner and
            everyone who may read the agent's conversations reads it.
        """

        return self.owner_user_id is None

    @property
    def pending_count_user_ids(self) -> list[int] | None:
        """
        :return: The users whose pending count the conversation's held calls add
            to: its owner, or None for everyone who may read the agent when it's
            shared, since those who may decide them depends on their role.
        """

        return None if self.is_shared else [self.owner_user_id]

    class Meta:
        ordering = ("-pinned", "-updated_on", "-id")
        indexes = [
            models.Index(
                fields=["agent", "owner_user", "-pinned", "-updated_on", "-id"],
                name="agent_conversation_pinned_idx",
            ),
            models.Index(
                fields=["agent", "-pinned", "-updated_on", "-id"],
                name="agent_conversation_shared_idx",
            ),
            # Rate limits count a trigger's, or its agent's, recent conversations.
            models.Index(
                fields=["trigger", "-created_on"],
                condition=Q(trigger__isnull=False),
                name="agent_conversation_trigger_idx",
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


GOING_REPLY_STATUSES = (AgentReplyStatus.RUNNING, AgentReplyStatus.WAITING)


class AgentMessage(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """A message as shown in a conversation, not as sent to the AI model."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TRIGGER = "trigger", "Trigger"

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
            # Only replies still queued or going: what the trigger rules look up.
            models.Index(
                fields=["conversation"],
                condition=Q(
                    status__in=(AgentReplyStatus.QUEUED, *GOING_REPLY_STATUSES)
                ),
                name="agent_message_active_idx",
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
        help_text="For an MCP tool or an action, a digest of what it was when the "
        "call was held. An approved call only runs while it's the same.",
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
