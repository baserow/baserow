import uuid

from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.mixins import BigAutoFieldMixin, CreatedAndUpdatedOnMixin
from baserow.core.models import Workspace

User = get_user_model()


class AssistantChat(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Model representing a chat with the AI assistant.
    """

    TITLE_MAX_LENGTH = 250

    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        IN_PROGRESS = "in_progress", "In progress"
        CANCELING = "canceling", "Canceling"

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique identifier for the chat. Can be provided by the client.",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user who owns the chat."
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace the chat belongs to.",
    )
    title = models.CharField(
        max_length=TITLE_MAX_LENGTH, blank=True, help_text="The title of the chat."
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDLE
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "workspace", "-updated_on"]),
        ]

    def __str__(self):
        return f"Chat: {self.title} ({self.user_id})"
