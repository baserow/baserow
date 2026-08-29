import uuid

from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.mixins import (
    BigAutoFieldMixin,
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
)
from baserow.core.models import Agent, Application
from baserow.core.services.models import Service

User = get_user_model()

__all__ = [
    "AgentApplication",
    "AgentDefinition",
    "AgentTrigger",
    "AgentTool",
    "AgentChatChannel",
    "AgentChat",
    "AgentChatMessage",
    "AgentChatToolApproval",
]


class AgentApplication(Application):
    description = models.TextField(
        blank=True,
        db_default="",
        help_text="What the agent should do, used to AI-configure the agent.",
    )
    active = models.BooleanField(
        default=False,
        db_default=False,
        help_text=(
            "Master switch: while off the agent only runs manually and its "
            "triggers never fire. Off by default so a new agent can be "
            "configured safely before going live."
        ),
    )
    agent_identity = models.ForeignKey(
        Agent,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "The workspace agent subject this application acts as. Without one "
            "the agent has no access to the workspace."
        ),
    )

    def get_parent(self):
        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr


class AgentDefinition(
    HierarchicalModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    """
    The configuration of a single agent within an agent application. An
    application holds exactly one agent for now; the separate table exists so
    that sub agents can later become additional rows with a parent relation.
    """

    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        related_name="agents",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, db_default="")
    instructions = models.TextField(blank=True, db_default="")
    memory = models.TextField(
        blank=True,
        db_default="",
        help_text=(
            "Persistent notes loaded into every run. Written by the agent "
            "itself (e.g. ids of things it created, lessons learned) and "
            "editable by users to teach the agent."
        ),
    )
    ai_generative_ai_type = models.CharField(
        max_length=32, null=True, blank=True, db_default=None
    )
    ai_generative_ai_model = models.CharField(
        max_length=128, null=True, blank=True, db_default=None
    )
    ai_temperature = models.FloatField(null=True, blank=True, db_default=None)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["application"],
                name="unique_agent_definition_per_application",
            )
        ]

    def get_parent(self):
        return self.application


class AgentTrigger(HierarchicalModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Connects an agent application to a trigger service. The trigger's service
    type determines when a new agent chat is started automatically. An
    application can have multiple triggers.
    """

    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        related_name="triggers",
    )
    service = models.OneToOneField(
        Service,
        on_delete=models.CASCADE,
        related_name="agent_trigger",
    )
    enabled = models.BooleanField(default=True, db_default=True)

    class Meta:
        ordering = ("id",)

    def get_parent(self):
        return self.application


class AgentTool(HierarchicalModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    A tool enabled for an agent. The `type` refers to an agent tool type in
    the registry; service-backed tools additionally point at a configured
    service that is dispatched when the model calls the tool.
    """

    agent = models.ForeignKey(
        AgentDefinition,
        on_delete=models.CASCADE,
        related_name="tools",
    )
    type = models.CharField(max_length=64)
    name = models.CharField(max_length=160, blank=True, db_default="")
    config = models.JSONField(default=dict, blank=True, db_default={})
    service = models.OneToOneField(
        Service,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="agent_tool",
    )
    order = models.PositiveIntegerField(default=1, db_default=1)

    class Meta:
        ordering = ("order", "id")

    def get_parent(self):
        return self.agent


class AgentChatChannel(HierarchicalModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Connects an agent application to an external chat surface (e.g. Slack)
    through which conversations with the agent can be started. The `type`
    refers to a chat channel type in the registry; the config holds the
    type-specific credentials.
    """

    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        related_name="chat_channels",
    )
    type = models.CharField(max_length=64)
    name = models.CharField(max_length=160, blank=True, db_default="")
    config = models.JSONField(default=dict, blank=True, db_default={})
    enabled = models.BooleanField(default=True, db_default=True)
    uid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unguessable token identifying this channel's inbound webhook URL.",
    )

    class Meta:
        ordering = ("id",)

    def get_parent(self):
        return self.application


class AgentChat(
    BigAutoFieldMixin,
    HierarchicalModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    """
    A conversation with an agent. Started manually by a user, by a trigger
    event, by an external chat channel, or by the AI-assisted setup of the
    agent.
    """

    TITLE_MAX_LENGTH = 250

    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        IN_PROGRESS = "in_progress", "In progress"
        CANCELING = "canceling", "Canceling"
        # The run is paused on tool calls waiting in the approval queue.
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        ERROR = "error", "Error"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        TRIGGER = "trigger", "Trigger"
        SETUP = "setup", "Setup"
        CHANNEL = "channel", "Channel"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    agent = models.ForeignKey(
        AgentDefinition,
        on_delete=models.CASCADE,
        related_name="chats",
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        help_text="The user who started the chat. Null for triggered chats.",
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH, blank=True, db_default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IDLE,
        db_default=Status.IDLE,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
        db_default=Source.MANUAL,
    )
    trigger_type = models.CharField(max_length=64, blank=True, db_default="")
    event_payload = models.JSONField(null=True, blank=True, db_default=None)
    channel = models.ForeignKey(
        AgentChatChannel,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="chats",
        help_text="The external chat channel this conversation belongs to.",
    )
    channel_session_key = models.CharField(
        max_length=255,
        blank=True,
        db_default="",
        help_text=(
            "Channel specific session identifier (e.g. Slack channel/thread) "
            "used to continue the same conversation across messages."
        ),
    )
    started_on = models.DateTimeField(null=True, blank=True, db_default=None)
    completed_on = models.DateTimeField(null=True, blank=True, db_default=None)
    error = models.TextField(blank=True, db_default="")
    message_history = models.BinaryField(
        null=True,
        blank=True,
        help_text=(
            "Serialized pydantic-ai message history (JSON bytes) for "
            "multi-turn conversation context."
        ),
    )
    total_input_tokens = models.BigIntegerField(default=0, db_default=0)
    total_output_tokens = models.BigIntegerField(default=0, db_default=0)

    class Meta:
        indexes = [
            models.Index(fields=["agent", "-updated_on"]),
            models.Index(fields=["agent", "status"]),
            models.Index(fields=["channel", "channel_session_key"]),
        ]

    def get_parent(self):
        return self.agent

    @property
    def is_running(self) -> bool:
        return self.status in (self.Status.IN_PROGRESS, self.Status.CANCELING)

    @property
    def is_awaiting_approval(self) -> bool:
        return self.status == self.Status.AWAITING_APPROVAL


class AgentChatMessage(
    BigAutoFieldMixin,
    HierarchicalModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    class Role(models.TextChoices):
        HUMAN = "human", "Human"
        AI = "ai", "AI"
        # System messages carry the trigger's opening prompt so the full
        # context of a triggered run is visible in the history.
        SYSTEM = "system", "System"

    chat = models.ForeignKey(
        AgentChat,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    artifacts = models.JSONField(
        default=dict,
        blank=True,
        db_default={},
        help_text="Structured extras such as tool calls and reasoning.",
    )
    attachments = models.JSONField(
        default=list,
        blank=True,
        db_default=[],
        help_text=(
            "User files attached to this message, as a list of dicts with at "
            "least the stored user file `name`. The files are injected into "
            "the model prompt of the turn this message starts."
        ),
    )
    input_tokens = models.IntegerField(null=True, blank=True, db_default=None)
    output_tokens = models.IntegerField(null=True, blank=True, db_default=None)

    class Meta:
        ordering = ("id",)

    def get_parent(self):
        return self.chat


class AgentChatToolApproval(
    BigAutoFieldMixin,
    HierarchicalModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    """
    A tool call that paused an agent run because it changes data and the tool
    is configured to require approval. The run resumes once every pending
    approval of the chat has been decided.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    chat = models.ForeignKey(
        AgentChat,
        on_delete=models.CASCADE,
        related_name="tool_approvals",
    )
    message = models.ForeignKey(
        AgentChatMessage,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="tool_approvals",
        help_text="The AI message during which the tool call was requested.",
    )
    tool_call_id = models.CharField(max_length=255)
    tool_name = models.CharField(max_length=255)
    tool_args = models.JSONField(null=True, blank=True, db_default=None)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_default=Status.PENDING,
    )
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True, db_default=None)
    reason = models.TextField(
        blank=True,
        db_default="",
        help_text="Optional rejection reason, returned to the model.",
    )

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=["chat", "status"])]

    def get_parent(self):
        return self.chat
