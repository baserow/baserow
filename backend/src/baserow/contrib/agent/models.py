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
    """Conversation activity owned by one agent, separate from its configuration."""

    class SourceType(models.TextChoices):
        """How a conversation starts, independently of who can access it."""

        # A user starts a conversation in the Agent's Baserow chat interface.
        INTERNAL_CHAT = "internal_chat", "Internal chat"
        # An automatic event, such as a schedule or a database change.
        TRIGGER = "trigger", "Trigger"
        # A message arriving through an external chat channel, such as Slack.
        EXTERNAL_CHAT = "external_chat", "External chat"
        # An explicit Run Agent service call from a button, workflow or agent.
        SERVICE = "service", "Service"

    class Visibility(models.TextChoices):
        """The intended audience, independent of the conversation's origin."""

        PRIVATE = "private", "Private"
        SHARED = "shared", "Shared"

    agent = models.ForeignKey(
        AgentApplication, on_delete=models.CASCADE, related_name="conversations"
    )
    uuid = models.UUIDField(unique=True)
    title = models.CharField(max_length=250)
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.INTERNAL_CHAT,
        db_default=SourceType.INTERNAL_CHAT,
        help_text=(
            "Where this conversation started; this does not control who can read it."
        ),
    )
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        db_default=Visibility.PRIVATE,
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ("-updated_on", "id")
        indexes = [
            models.Index(
                fields=["agent", "owner_user", "-updated_on", "id"],
                name="agent_conversation_owner_idx",
            ),
        ]


class AgentMessage(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """A persisted transcript message, separate from the model's protocol history."""

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
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.SET_NULL,
        related_name="+",
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
