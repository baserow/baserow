from dataclasses import asdict, dataclass

from django.dispatch import receiver
from django.utils.translation import gettext as _

from loguru import logger

from baserow.core.notifications.exceptions import NotificationDoesNotExist
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.registries import (
    CliNotificationTypeMixin,
    EmailNotificationTypeMixin,
    NotificationType,
)

from .signals import (
    workspace_invitation_accepted,
    workspace_invitation_rejected,
    workspace_invitation_updated_or_created,
)


@dataclass
class InvitationNotificationData:
    invitation_id: int
    invited_to_workspace_id: int
    invited_to_workspace_name: str


def mark_invitation_notification_as_read(user, invitation):
    try:
        notification = NotificationHandler.get_notification_by(
            user,
            notificationrecipient__read=False,
            data__contains={"invitation_id": invitation.id},
        )
    except NotificationDoesNotExist:
        return

    NotificationHandler.mark_notification_as_read(
        user, notification, include_user_in_signal=True
    )


class WorkspaceInvitationCreatedNotificationType(NotificationType):
    type = "workspace_invitation_created"

    @classmethod
    def create_notification(cls, invitation, invited_user):
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=[invited_user],
            sender=invitation.invited_by,
            data=asdict(
                InvitationNotificationData(
                    invitation.id, invitation.workspace.id, invitation.workspace.name
                )
            ),
        )


@receiver(workspace_invitation_updated_or_created)
def notify_invited_user(sender, invitation, invited_user, created, **kwargs):
    if invited_user is not None and created:
        WorkspaceInvitationCreatedNotificationType.create_notification(
            invitation, invited_user
        )


class WorkspaceInvitationAcceptedNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "workspace_invitation_accepted"

    @classmethod
    def create_invitation_accepted_notification(cls, user, invitation):
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=[invitation.invited_by],
            sender=user,
            data=asdict(
                InvitationNotificationData(
                    invitation.id, invitation.workspace.id, invitation.workspace.name
                )
            ),
            workspace=invitation.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(user)s accepted your invitation to collaborate on %(workspace_name)s."
        ) % {
            "user": notification.sender.first_name,
            "workspace_name": notification.data["invited_to_workspace_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return None


@receiver(workspace_invitation_accepted)
def handle_workspace_invitation_accepted(sender, invitation, user, **kwargs):
    mark_invitation_notification_as_read(user, invitation)
    WorkspaceInvitationAcceptedNotificationType.create_invitation_accepted_notification(
        user, invitation
    )


class WorkspaceInvitationRejectedNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "workspace_invitation_rejected"

    @classmethod
    def create_invitation_rejected_notification(cls, user, invitation):
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=[invitation.invited_by],
            sender=user,
            data=asdict(
                InvitationNotificationData(
                    invitation.id, invitation.workspace.id, invitation.workspace.name
                )
            ),
            workspace=invitation.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(user)s rejected your invitation to collaborate on %(workspace_name)s."
        ) % {
            "user": notification.sender.first_name,
            "workspace_name": notification.data["invited_to_workspace_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return None


@receiver(workspace_invitation_rejected)
def handle_workspace_invitation_rejected(sender, invitation, user, **kwargs):
    mark_invitation_notification_as_read(user, invitation)
    WorkspaceInvitationRejectedNotificationType.create_invitation_rejected_notification(
        user, invitation
    )


class BaserowVersionUpgradeNotificationType(CliNotificationTypeMixin, NotificationType):
    type = "baserow_version_upgrade"

    @classmethod
    def create_version_upgrade_broadcast_notification(
        cls, version, release_notes_url=None
    ):
        NotificationHandler.create_broadcast_notification(
            notification_type=cls.type,
            sender=None,
            data={"version": version, "release_notes_url": release_notes_url},
        )

    @classmethod
    def prompt_for_args_in_cli_and_create_notification(cls):
        version = input("Enter the version number (i.e. 1.19): ")
        if not version:
            print("Version is required.")
            return

        release_notes_url = input(
            "Enter the release notes URL (i.e. https://baserow.io/blog/1-19-release-of-baserow): "
        )

        confirm = input(
            "Are you sure you want to create a notification with these data?\n\n"
            f"Version: {version}\n"
            f"Release notes URL: {release_notes_url}\n\n"
            "Enter 'y' to confirm: "
        )
        if confirm.lower() == "y":
            cls.create_version_upgrade_broadcast_notification(
                version, release_notes_url
            )
            logger.info(
                f"Broadcast notification {cls.type} successfully created via CLI."
            )
