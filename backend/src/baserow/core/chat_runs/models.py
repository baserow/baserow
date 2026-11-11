import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

User = get_user_model()


class ChatRunStatus(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


ACTIVE_CHAT_RUN_STATUSES = (ChatRunStatus.QUEUED.value, ChatRunStatus.RUNNING.value)


class ChatRun(models.Model):
    """
    One background execution answering one chat message. Everything product
    specific belongs to the run type, identified by `run_type`, and the chat it
    answers in is identified by `run_type` and `chat_id` together.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_type = models.CharField(max_length=32)
    chat_id = models.BigIntegerField()
    workspace = models.ForeignKey(
        "core.Workspace", on_delete=models.CASCADE, related_name="+"
    )
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=16, choices=ChatRunStatus.choices, default=ChatRunStatus.QUEUED
    )
    error_code = models.CharField(max_length=64, blank=True, default="")
    context = models.JSONField(default=dict)
    # Serialized product outcome, written only during terminal finalization.
    outcome = models.JSONField(null=True)
    cancel_requested_at = models.DateTimeField(null=True)
    # Not indexed, so the frequent renewals stay cheap updates.
    lease_expires_at = models.DateTimeField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    started_on = models.DateTimeField(null=True)
    finished_on = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["run_type", "chat_id", "-created_on"],
                name="chat_run_conversation_created",
            ),
            models.Index(fields=["finished_on"], name="chat_run_finished"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run_type", "chat_id"],
                condition=Q(status__in=ACTIVE_CHAT_RUN_STATUSES),
                name="chat_run_one_active_per_chat",
            )
        ]
