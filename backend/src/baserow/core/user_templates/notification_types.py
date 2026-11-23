from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Template
from baserow.core.notifications.handler import (
    NotificationHandler,
    UserNotificationsGrouper,
)
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import NotificationType
from baserow.core.user.utils import active_instance_admins


@dataclass
class UserTemplateNotificationData:
    template_id: int
    template_name: str

    @classmethod
    def from_revision(cls, revision: Template) -> "UserTemplateNotificationData":
        return cls(
            template_id=revision.root_id or revision.id,
            template_name=revision.name,
        )


@dataclass
class UserTemplateAuthorNotificationData(UserTemplateNotificationData):
    template_slug: str
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.reason is None:
            del data["reason"]
        return data


class UserTemplateNotificationType(NotificationType):
    @classmethod
    def notify_admins(
        cls,
        revision: Template,
        exclude: AbstractUser,
        only_unnotified: bool = False,
    ) -> List[NotificationRecipient]:
        """
        Notifies the active instance admins about a revision of a user template.
        Shown in every workspace.

        :param revision: The revision the notification is about.
        :param exclude: The user who caused it, who isn't notified.
        :param only_unnotified: Whether admins who haven't read a notification of
            this type about the template yet are left out.
        :return: The created notification recipients.
        """

        data = UserTemplateNotificationData.from_revision(revision)
        admins = active_instance_admins().exclude(id=exclude.id)
        if only_unnotified:
            admins = admins.exclude(
                id__in=NotificationRecipient.objects.filter(
                    read=False,
                    notification__type=cls.type,
                    notification__data__contains={"template_id": data.template_id},
                ).values("recipient_id")
            )

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=admins,
            data=asdict(data),
            sender=None,
            workspace=None,
        )

    @classmethod
    def notify_author(
        cls,
        revision: Template,
        root: Template,
        actor: AbstractUser,
        reason: Optional[str] = None,
    ) -> List[NotificationRecipient]:
        """
        Notifies the owner of a user template about a revision of it, unless the
        owner is the one who caused it. Shown in every workspace.

        :param revision: The revision the notification is about.
        :param root: The root of the template, which has its owner and slug.
        :param actor: The user who caused it.
        :param reason: Why it happened, shown to the owner, if any.
        :return: The created notification recipients.
        """

        data = cls._author_data(revision, root.owner_id, root.slug, actor, reason)
        if data is None:
            return []
        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=[root.owner],
            data=data,
            sender=None,
            workspace=None,
        )

    @classmethod
    def notify_authors_in_bulk(
        cls,
        rows: Iterable[Tuple[Template, Optional[int], str]],
        actor: AbstractUser,
    ) -> None:
        """
        Notifies the owners of many user templates at once, except the one who
        caused it. Shown in every workspace.

        :param rows: The revision each notification is about, the id of the owner
            of its template, and the slug of its root.
        :param actor: The user who caused it.
        """

        grouper = UserNotificationsGrouper()
        for revision, owner_id, slug in rows:
            data = cls._author_data(revision, owner_id, slug, actor)
            if data is not None:
                notification = NotificationHandler.construct_notification(
                    cls.type, data=data
                )
                grouper.add(notification, [owner_id])
        if grouper.has_notifications_to_send():
            grouper.create_all_notifications_and_trigger_task()

    @staticmethod
    def _author_data(
        revision: Template,
        owner_id: Optional[int],
        slug: str,
        actor: AbstractUser,
        reason: Optional[str] = None,
    ) -> Optional[dict]:
        """
        What the notification to the owner of a user template carries.

        :return: The data, None when the template has no owner or the owner
            caused it.
        """

        if owner_id in (None, actor.id):
            return None
        return UserTemplateAuthorNotificationData(
            **asdict(UserTemplateNotificationData.from_revision(revision)),
            template_slug=slug,
            reason=reason,
        ).to_dict()


class UserTemplateInReviewNotificationType(UserTemplateNotificationType):
    type = "user_template_in_review"


class BlockedUserTemplateChangedNotificationType(UserTemplateNotificationType):
    type = "blocked_user_template_changed"


class UserTemplateApprovedNotificationType(UserTemplateNotificationType):
    type = "user_template_approved"


class UserTemplateRejectedNotificationType(UserTemplateNotificationType):
    type = "user_template_rejected"


class UserTemplateBlockedNotificationType(UserTemplateNotificationType):
    type = "user_template_blocked"


class UserTemplateUnblockedNotificationType(UserTemplateNotificationType):
    type = "user_template_unblocked"
