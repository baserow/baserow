import uuid
from django.db import models
from django.db.models import F
from django.contrib.auth import get_user_model

from baserow.core.models import Workspace
from baserow.core.mixins import CreatedAndUpdatedOnMixin, BigAutoFieldMixin

User = get_user_model()


class AssistantChat(BigAutoFieldMixin, CreatedAndUpdatedOnMixin, models.Model):
    """
    Model representing a chat with the AI assistant.
    """

    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        IN_PROGRESS = "in_progress", "In progress"
        CANCELING = "canceling", "Canceling"

    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    context = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDLE
    )

    def __str__(self):
        return f"Chat: {self.title} ({self.user_id})"
