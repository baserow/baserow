from rest_framework import serializers

from baserow.core.notifications.models import NotificationRecipient, User
from baserow.core.user.identity import is_human_user


class SenderSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    def get_username(self, instance) -> str | None:
        return instance.username if is_human_user(instance) else None

    class Meta:
        model = User
        fields = ("id", "username", "first_name")


class NotificationRecipientSerializer(serializers.ModelSerializer):
    """
    Serialize notification data along with the recipient information about the
    read status for the given user.
    """

    id = serializers.IntegerField(
        source="notification.id", help_text="The id of the notification."
    )
    type = serializers.CharField(
        source="notification.type",
        help_text="The type of notification",
    )
    sender = SenderSerializer(
        source="notification.sender", help_text="The user that sent the notification."
    )
    data = serializers.JSONField(
        source="notification.data",
        help_text="The data associated with the notification.",
    )
    workspace = serializers.SerializerMethodField(
        read_only=True, help_text="The workspace that the notification is in (if any)."
    )
    created_on = serializers.DateTimeField(
        source="notification.created_on",
        help_text="The date and time that the notification was created.",
    )

    def get_workspace(self, instance):
        if instance.workspace_id:
            return {"id": instance.workspace_id}
        return None

    class Meta:
        model = NotificationRecipient
        fields = (
            "id",
            "type",
            "sender",
            "workspace",
            "created_on",
            "read",
            "data",
        )


class NotificationUpdateSerializer(serializers.Serializer):
    read = serializers.BooleanField(
        help_text="If True, then the notification has been read by the recipient.",
    )

    class Meta:
        fields = ("read",)
        extra_kwargs = {
            "read": {"read_only": True},
        }
