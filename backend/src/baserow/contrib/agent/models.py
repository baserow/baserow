from django.conf import settings
from django.db import models

from baserow.core.mixins import BigAutoFieldMixin, CreatedAndUpdatedOnMixin
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


class AgentConversation(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
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

    class Meta:
        ordering = ("-updated_on", "id")
        indexes = [
            models.Index(
                fields=["agent", "owner_user", "-updated_on", "id"],
                name="agent_conversation_owner_idx",
            ),
        ]


class AgentTurn(BigAutoFieldMixin, models.Model):
    """The agent's answer to one prompt, from sending it to the final outcome."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name="turns"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RUNNING
    )
    error_code = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ("id",)


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
    turn = models.ForeignKey(
        AgentTurn, null=True, on_delete=models.CASCADE, related_name="messages"
    )

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
