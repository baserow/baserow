from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

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
            template_id=revision.family_id,
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
    def last_decider_id(cls, template_id: int) -> Optional[int]:
        """
        The admin who last decided on the template, who alone is notified about it
        while still an active instance admin.

        :param template_id: The id of the template, which is its root.
        :return: The id of the admin, None if no one is.
        """

        return None

    @classmethod
    def notify_admins(
        cls, revision: Template, author: AbstractUser
    ) -> List[NotificationRecipient]:
        """
        Notifies the active instance admins about a revision of a user template,
        only the last decider when there's one, see `last_decider_id`. Admins who
        haven't read a notification of this type about the template yet are left
        out. Shown in every workspace.

        :param revision: The revision the notification is about.
        :param author: The owner of the template, who isn't notified and whose
            first name the notification carries.
        :return: The created notification recipients.
        """

        data = UserTemplateNotificationData.from_revision(revision)
        admins = active_instance_admins().exclude(id=author.id)
        decider_id = cls.last_decider_id(data.template_id)
        if decider_id is not None and admins.filter(id=decider_id).exists():
            admins = admins.filter(id=decider_id)
        admins = admins.exclude(
            id__in=unread_recipients([cls.type], [data.template_id]).values(
                "recipient_id"
            )
        )

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=admins,
            data={**asdict(data), "author_name": author.first_name},
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

    @classmethod
    def last_decider_id(cls, template_id: int) -> Optional[int]:
        return (
            Template.objects.filter_by_root(id=template_id)
            .exclude(reviewed_on=None)
            .order_by("-reviewed_on")
            .values_list("reviewed_by_id", flat=True)
            .first()
        )


class BlockedUserTemplateChangedNotificationType(UserTemplateNotificationType):
    type = "blocked_user_template_changed"

    @classmethod
    def last_decider_id(cls, template_id: int) -> Optional[int]:
        return (
            Template.objects.filter(id=template_id)
            .values_list("blocked_by_id", flat=True)
            .first()
        )


class UserTemplateApprovedNotificationType(UserTemplateNotificationType):
    type = "user_template_approved"


class UserTemplateRejectedNotificationType(UserTemplateNotificationType):
    type = "user_template_rejected"


class UserTemplateChangeRejectedNotificationType(UserTemplateNotificationType):
    type = "user_template_change_rejected"


class UserTemplateUnlistedNotificationType(UserTemplateNotificationType):
    type = "user_template_unlisted"


class UserTemplateBlockedNotificationType(UserTemplateNotificationType):
    type = "user_template_blocked"


class UserTemplateUnblockedNotificationType(UserTemplateNotificationType):
    type = "user_template_unblocked"


def unread_recipients(types: List[str], template_ids: Iterable[int]) -> QuerySet:
    """
    The recipients who haven't read a notification of the types about the
    templates yet.

    :param types: The notification types.
    :param template_ids: The ids of the templates, which are their roots.
    :return: A queryset of the notification recipients.
    """

    about_templates = Q()
    for template_id in template_ids:
        about_templates |= Q(notification__data__contains={"template_id": template_id})
    if not about_templates:
        return NotificationRecipient.objects.none()
    return NotificationRecipient.objects.filter(
        about_templates, read=False, notification__type__in=types
    )


def mark_admin_notifications_read(template_ids: Iterable[int]) -> None:
    """
    Marks the unread admin notifications about the templates as read, once an
    admin decided on them.

    :param template_ids: The ids of the templates, which are their roots.
    """

    NotificationHandler.mark_recipients_as_read(
        unread_recipients(
            [
                UserTemplateInReviewNotificationType.type,
                BlockedUserTemplateChangedNotificationType.type,
            ],
            template_ids,
        )
    )
