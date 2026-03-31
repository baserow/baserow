from django.contrib.auth import get_user_model
from django.contrib.postgres.indexes import GinIndex
from django.db import models

User = get_user_model()


class Notification(models.Model):
    created_on = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time when the notification was created.",
    )
    type = models.CharField(max_length=64, help_text="The type of notification.")
    broadcast = models.BooleanField(
        default=False,
        help_text=(
            "If True, then the notification will be sent to all users. "
            "A broadcast notification will not immediately create all the "
            "NotificationRecipient objects, but will do so when the "
            "notification is read or cleared by a user."
        ),
    )
    workspace = models.ForeignKey(
        "core.Workspace",
        null=True,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text=(
            "The workspace where the notification lives."
            "If the notification is a broadcast notification, then the "
            "workspace will be None."
            "Workspace can be null also if the notification is not "
            "associated with a specific workspace or if the user does not "
            "have access to the workspace yet, like for a workspace invitation."
        ),
    )
    sender = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sent_notifications",
        help_text="The user that will receive the notification.",
    )
    recipients = models.ManyToManyField(
        User,
        through="NotificationRecipient",
        related_name="notifications",
        help_text=(
            "The users that will receive the notification. For broadcast "
            "notifications, the recipients will be created when the "
            "notification is read or cleared by the user."
            "For direct notifications, the recipients will be created "
            "immediately when the notification is created."
        ),
    )
    data = models.JSONField(default=dict, help_text="The data of the notification.")

    @property
    def web_frontend_url(self):
        from .registries import notification_type_registry

        notification_type = notification_type_registry.get(self.type)
        return notification_type.get_web_frontend_url(self)

    class Meta:
        ordering = ["-created_on", "-id"]
        indexes = [
            models.Index(fields=["-created_on", "-id"]),
            GinIndex(name="notification_data", fields=["data"]),
        ]


class NotificationRecipient(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        help_text="The notification that will be sent to the recipient.",
    )
    recipient = models.ForeignKey(
        User,
        null=True,
        on_delete=models.CASCADE,
        help_text="The user that will receive the notification.",
    )
    read = models.BooleanField(
        default=False,
        help_text=("If True, then the notification has been read by the user. "),
    )
    cleared = models.BooleanField(
        default=False,
        help_text=(
            "If True, then the notification has been cleared by the user. "
            "Cleared notifications will not be visible by the user anymore."
        ),
    )
    queued = models.BooleanField(
        default=False,
        help_text=(
            "If True, then the notification has been queued for sending. "
            "Queued notifications cannot be seen by the user yet. "
            "Once the notification has been sent, this field will be "
            "set to False and the user will be able to fetch it via API."
        ),
    )
    email_scheduled = models.BooleanField(
        default=False,
        help_text=(
            "If True, then the notification has been scheduled to be sent by email "
            "to the recipient email."
        ),
    )
    # The following fields are copies of the notification fields needed to
    # speed up queries.
    created_on = models.DateTimeField(
        help_text="A copy of the notification created_on field needed to speed up queries.",
    )
    broadcast = models.BooleanField(
        default=False,
        help_text=(
            "A copy of the notification broadcast field needed to speed up queries."
        ),
    )
    workspace_id = models.BigIntegerField(
        null=True,
        help_text=(
            "A copy of the notification workspace_id field needed to speed up queries."
        ),
    )

    class Meta:
        ordering = ["-created_on", "-id"]
        unique_together = ("notification", "recipient")
        indexes = [
            models.Index(fields=["-created_on", "-id"]),
            models.Index(
                fields=[
                    "broadcast",
                    "cleared",
                    "read",
                    "queued",
                    "recipient_id",
                    "workspace_id",
                ],
                name="unread_notif_count_idx",
                condition=models.Q(cleared=False, read=False),
                include=["notification_id"],
            ),
        ]
