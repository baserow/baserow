import inspect
from datetime import datetime, timezone
from typing import Any, Dict, List, NamedTuple, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.mail import get_connection as get_mail_connection
from django.db import transaction
from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.utils import translation

from loguru import logger
from opentelemetry import trace

from baserow.core.emails import NotificationsSummaryEmail
from baserow.core.models import User, UserProfile, Workspace
from baserow.core.telemetry.utils import baserow_trace
from baserow.core.utils import (
    atomic_if_not_already,
    grouper,
    transaction_on_commit_if_not_already,
)

from .exceptions import NotificationDoesNotExist
from .models import Notification, NotificationRecipient
from .registries import notification_type_registry
from .signals import (
    all_notifications_cleared,
    all_notifications_marked_as_read,
    notification_created,
    notification_marked_as_read,
)
from .tasks import send_queued_notifications_to_users

tracer = trace.get_tracer(__name__)


NOTIFICATIONS_WITH_EMAIL_SCHEDULED_FILTERS = {
    "queued": False,
    "read": False,
    "email_scheduled": True,
}


class UserWithScheduledEmailNotifications(NamedTuple):
    """
    A named tuple containing a list of users with notifications that are
    scheduled to be sent via email and the number of users that are not
    included in the list, but have notifications that need to be sent via
    email.
    """

    users_with_notifications: List[AbstractUser]
    remaining_users_to_notify_count: int = 0


class NotificationHandler:
    @classmethod
    def _get_unread_broadcast_q(cls, user: AbstractUser) -> Q:
        user_broadcast = NotificationRecipient.objects.filter(
            broadcast=True, recipient=user
        )
        unread_broadcast = Q(broadcast=True, recipient=None) & ~Q(
            notification_id__in=user_broadcast.values("notification_id")
        )
        return unread_broadcast

    @classmethod
    @baserow_trace(tracer)
    def get_notification_by_id(
        cls, user: AbstractUser, notification_id: int
    ) -> NotificationRecipient:
        """
        Get a notification for the given user matching the given notification
        id.

        :param user: The user to get the notification for.
        :param notification_id: The id of the notification.
        :return: The notification recipient instance.
        :raises BaseNotificationDoesNotExist: When the notification with the
            given id does not exist or the given user is not a recipient for it.
        """

        return cls.get_notification_by(user, id=notification_id)

    @classmethod
    @baserow_trace(tracer)
    def get_notification_by(cls, user: AbstractUser, **kwargs) -> Notification:
        """
        Get a notification for the given user matching the given kwargs.

        :param user: The user to get the notification for.
        :return: The notification instance.
        :raises BaseNotificationDoesNotExist: When the notification with the
            given id does not exist or the given user is not a recipient for it.
        """

        unread_broadcast = cls._get_unread_broadcast_q(user)

        notification_ids = NotificationRecipient.objects.filter(
            Q(recipient=user, cleared=False) | unread_broadcast
        ).values("notification_id")

        result = Notification.objects.filter(id__in=notification_ids, **kwargs)

        # Get the caller function, skipping the otel wrapper
        caller = inspect.stack()[2].function

        if len(result) == 0:
            raise NotificationDoesNotExist(
                f"No notification found from {caller} for user {user.email} with the given filters."
            )
        elif len(result) > 1:
            # This means that there are multiple notifications matching the
            # given filters. This should not happen but it shouldn't be a
            # problem to return any of them, so we just return the first one
            # and log the event.
            # Get the caller function
            logger.error(
                f"{len(result)} notifications found from {caller} for user {user.email} "
                f"with the given filters {kwargs}. This should not happen, but it shouldn't "
                "be a problem to return any of them. Returning the first one.",
            )
        return result[0]

    @classmethod
    @baserow_trace(tracer)
    def all_notifications_for_user(
        cls, user, include_workspace: Optional[Workspace] = None
    ):
        workspace_filter = Q(workspace_id=None)
        if include_workspace is not None:
            workspace_filter |= Q(workspace_id=include_workspace.id)

        direct = Q(broadcast=False, recipient=user, queued=False) & workspace_filter
        uncleared_broadcast = Q(broadcast=True, recipient=user, cleared=False)
        unread_broadcast = cls._get_unread_broadcast_q(user)

        return NotificationRecipient.objects.filter(
            direct | uncleared_broadcast | unread_broadcast
        )

    @classmethod
    @baserow_trace(tracer)
    def list_notifications(cls, user, workspace: Workspace):
        """
        Returns a list of notifications for the given user and workspace.
        Broadcast notifications recipients are missing for the unread notifications,
        so we need to return them excluding the ones the user has already cleared.


        :param user: The user to get the notifications for.
        :param workspace: The workspace to get the notifications for.
        :return: A list of notifications.
        """

        return cls.all_notifications_for_user(user, workspace).select_related(
            "notification", "notification__sender"
        )

    @classmethod
    @baserow_trace(tracer)
    def get_unread_notifications_count(
        cls, user: AbstractUser, workspace: Optional[Workspace] = None
    ) -> int:
        """
        Returns the number of unread notifications for the given user. The count
        will include unread direct and broadcast user notifications (the ones
        with workspace_id=None). If a workspace is provided, also the unread
        notifications for that workspace will be counted.

        :param user: The user to count the notifications for.
        :param workspace: The workspace to count the notifications for. If not
            provided, only direct user notifications are counted (the ones with
            workspace_id=None).
        :return: The number of unread notifications.
        """

        workspace_q = Q(workspace_id=None)
        if workspace:
            workspace_q |= Q(workspace_id=workspace.id)

        unread_direct = (
            Q(broadcast=False, recipient=user, read=False, cleared=False, queued=False)
            & workspace_q
        )
        unread_broadcast = cls._get_unread_broadcast_q(user)

        return NotificationRecipient.objects.filter(
            unread_direct | unread_broadcast
        ).count()

    @classmethod
    @baserow_trace(tracer)
    def annotate_workspaces_with_unread_notifications_count(
        cls, user: AbstractUser, workspace_queryset: QuerySet, outer_ref_key: str = "pk"
    ) -> QuerySet:
        """
        Annotates the given workspace queryset with the number of unread notifications
        for the given user.

        :param user: The user to count the notifications for.
        :param workspace_queryset: The workspace queryset to annotate.
        :param outer_ref_key: The key to use for the outer ref.
        :return: The annotated workspace queryset.
        """

        notification_qs = NotificationRecipient.objects.filter(
            recipient=user,
            workspace_id=OuterRef(outer_ref_key),
            broadcast=False,
            read=False,
            cleared=False,
            queued=False,
        )

        subquery = Subquery(
            notification_qs.values("workspace_id")
            .annotate(count=Count("id"))
            .values("count")
        )

        return workspace_queryset.annotate(
            unread_notifications_count=Coalesce(subquery, 0)
        )

    @classmethod
    @baserow_trace(tracer)
    def _get_missing_broadcast_entries_for_user(
        cls,
        user: AbstractUser,
    ) -> QuerySet[NotificationRecipient]:
        """
        Because broadcast entries are created for user only when they mark them
        as read or cleared, this function returns the missing broadcast entries
        for the given user.

        :param user: The user to get the notifications for.
        :return: The missing broadcast notification recipients for the given
            user.
        """

        unread_broadcasts = cls._get_unread_broadcast_q(user)

        return NotificationRecipient.objects.filter(unread_broadcasts).select_related(
            "notification"
        )

    @classmethod
    @baserow_trace(tracer)
    def _create_missing_entries_for_broadcast_notifications_with_defaults(
        cls, user: AbstractUser, read=False, cleared=False, **kwargs
    ):
        """
        Broadcast entries might be missing because are created only when the
        user mark them as read or cleared, so let's create them and mark them as
        cleared so they don't show up anymore but also they are not recreated
        when the user clears all notifications again.

        :param user: The user to create the NotificationRecipient for.
        :param read: If True, the created NotificationRecipient will be marked as read.
        :param cleared: If True, the created NotificationRecipient will be marked as
            cleared.
        :param kwargs: Extra kwargs to pass to the NotificationRecipient constructor.
        :return: None
        """

        missing_broadcasts_entries = cls._get_missing_broadcast_entries_for_user(user)

        for missing_entries_chunk in grouper(1000, missing_broadcasts_entries):
            NotificationRecipient.objects.bulk_create(
                [
                    cls.construct_notification_recipient(
                        recipient=user,
                        notification=empty_entry.notification,
                        read=read,
                        cleared=cleared,
                        email_scheduled=False,
                        **kwargs,
                    )
                    for empty_entry in missing_entries_chunk
                ],
                ignore_conflicts=True,
            )

    @classmethod
    @baserow_trace(tracer)
    def clear_all_notifications(
        cls,
        user: AbstractUser,
        workspace: Workspace,
    ):
        """
        Clears all the notifications for the given user and workspace. Broadcast
        notifications are cleared setting the cleared flag to True for the
        recipient. Direct notifications are cleared deleting the
        NotificationRecipient entries. If a direct notification ends up without
        recipients, it will be deleted as well.

        :param user: The user to clear the notifications for.
        :param workspace: The workspace to clear the notifications for.
        """

        cls._create_missing_entries_for_broadcast_notifications_with_defaults(
            user, cleared=True
        )

        # Mark all broadcast recipients as cleared. The recipient object cannot
        # be deleted in this case because it will result in an unread
        # notification instead.
        broadcast_recipients = NotificationRecipient.objects.filter(
            broadcast=True, recipient=user, cleared=False
        )
        broadcast_recipients.update(cleared=True)

        # Direct recipients must be deleted. If a notification ends
        # up without recipients, it will be deleted as well.
        direct_recipients = NotificationRecipient.objects.filter(
            Q(workspace_id=workspace.pk) | Q(workspace_id=None),
            recipient=user,
            broadcast=False,
            cleared=False,
            queued=False,
        )

        Notification.objects.annotate(recipient_count=Count("recipients")).filter(
            Q(workspace_id=workspace.pk) | Q(workspace_id=None),
            broadcast=False,
            recipient_count=1,
            id__in=direct_recipients.values("notification_id"),
        ).delete()
        direct_recipients.delete()

        all_notifications_cleared.send(sender=cls, user=user, workspace=workspace)

    @classmethod
    @baserow_trace(tracer)
    def mark_notification_as_read(
        cls,
        user: AbstractUser,
        notification: Notification,
        read: bool = True,
        include_user_in_signal: bool = False,
    ) -> NotificationRecipient:
        """
        Marks a notification as read for the given user and returns the updated
        notification instance.

        :param user: The user to mark the notifications as read for.
        :param notification: The notification to mark as read.
        :param read: If True, the notification will be marked as read, otherwise
            it will be marked as unread.
        :param include_user_in_signal: Since the notification can be
            automatically marked as read by the system, this parameter can be
            used to include the user session in the real time event.
        :return: The notification instance updated.
        """

        notification_recipient, _ = NotificationRecipient.objects.update_or_create(
            notification=notification,
            recipient=user,
            defaults={
                "read": read,
                "workspace_id": notification.workspace_id,
                "broadcast": notification.broadcast,
                "created_on": notification.created_on,
                "email_scheduled": False,
            },
        )

        # If the notification is automatically marked as read as a side effect
        # of another action, we want to send this real time event also to the
        # user that triggered it.
        ignore_web_socket_id = getattr(user, "web_socket_id", None)
        if include_user_in_signal:
            ignore_web_socket_id = None

        notification_marked_as_read.send(
            sender=cls,
            notification=notification,
            notification_recipient=notification_recipient,
            user=user,
            ignore_web_socket_id=ignore_web_socket_id,
        )

        return notification_recipient

    @classmethod
    @baserow_trace(tracer)
    def mark_all_notifications_as_read(cls, user: AbstractUser, workspace: Workspace):
        """
        Marks all the notifications as read for the given workspace and user.

        :param user: The user to mark the notifications as read for.
        :param workspace: The workspace to filter the notifications by.
        """

        cls._create_missing_entries_for_broadcast_notifications_with_defaults(
            user, read=True
        )

        NotificationRecipient.objects.filter(
            Q(workspace_id=workspace.pk) | Q(workspace_id=None),
            recipient=user,
            read=False,
            cleared=False,
            queued=False,
        ).update(read=True, email_scheduled=False)

        all_notifications_marked_as_read.send(
            sender=cls, user=user, workspace=workspace
        )

    @classmethod
    @baserow_trace(tracer)
    def construct_notification(
        cls, notification_type: str, sender=None, data=None, workspace=None, **kwargs
    ) -> Notification:
        """
        Create the notification with the provided data.

        :param notification_type: The type of the notification.
        :param sender: The user that sent the notification.
        :param data: The data that will be stored in the notification.
        :param workspace: The workspace that the notification is linked to.
        :return: The constructed notification instance. Be aware that this
            instance is not saved yet.
        """

        return Notification(
            type=notification_type,
            sender=sender if sender and sender.is_authenticated else None,
            data=data or {},
            workspace=workspace,
            **kwargs,
        )

    @classmethod
    @baserow_trace(tracer)
    def construct_notification_recipient(
        cls,
        notification: Notification,
        recipient: Optional[AbstractUser] = None,
        read=False,
        cleared=False,
        queued=False,
        **kwargs,
    ) -> NotificationRecipient:
        """
        Create the notification recipient with the provided data, copying
        necessary data from the provided notification.

        :param notification: The notification to reference and to copy data
            from.
        :param recipient: The user that the notification is for. The recipient
            should be a valid user for direct notifications, while it can be
            None when the broadcast notification is created.
        :param read: If True, the notification will be marked as read.
        :param cleared: If True, the notification will be marked as cleared.
        :param queued: If True, the notification will be marked as queued.
        :param kwargs: Any additional data to be stored in the notification
            recipient.
        :return: The constructed notification recipient instance. Be aware that
            this instance is not saved yet.
        """

        email_scheduled = kwargs.pop("email_scheduled", None)
        if email_scheduled is None:
            notification_can_be_included_in_email = notification_type_registry.get(
                notification.type
            ).include_in_notifications_email

            # NOTE: Ensure to "select_related" user's profile before calling this
            # function for bulk_create notifications to avoid N+1 queries.
            recipient_wants_email = (
                recipient
                and recipient.profile.email_notification_frequency
                != UserProfile.EmailNotificationFrequencyOptions.NEVER
            )

            email_scheduled = (
                notification_can_be_included_in_email and recipient_wants_email
            )

        return NotificationRecipient(
            recipient=recipient,
            notification=notification,
            created_on=notification.created_on,
            broadcast=notification.broadcast,
            workspace_id=notification.workspace_id,
            read=read,
            cleared=cleared,
            queued=queued,
            email_scheduled=email_scheduled,
            **kwargs,
        )

    @classmethod
    @baserow_trace(tracer)
    def create_notification(
        cls, notification_type: str, sender=None, data=None, workspace=None, **kwargs
    ) -> Notification:
        """
        Create the notification with the provided data.

        :param notification_type: The type of the notification.
        :param sender: The user that sent the notification.
        :param data: The data that will be stored in the notification.
        :param workspace: The workspace that the notification is linked to.
        :param save: If True the notification will be saved in the database.
        :return: The created notification instance.
        """

        notification = cls.construct_notification(
            notification_type=notification_type,
            sender=sender,
            data=data,
            workspace=workspace,
            **kwargs,
        )

        notification.save()

        return notification

    @classmethod
    @baserow_trace(tracer)
    def create_broadcast_notification(
        cls,
        notification_type: str,
        sender=None,
        data=None,
        **kwargs,
    ) -> Notification:
        """
        Create the notification with the provided data.

        :param notification_type: The type of the notification.
        :param sender: The user that sent the notification.
        :param data: The data that will be stored in the notification.
        :param workspace: The workspace that the notification is linked to.
        :param save: If True the notification will be saved in the database.
        :return: The created notification instance.
        """

        notification = cls.create_notification(
            notification_type=notification_type,
            sender=sender,
            data=data,
            workspace=None,
            broadcast=True,
            **kwargs,
        )

        # With recipient=None we create a placeholder that will be
        # used as template to copy data from when users read/clear
        # this broadcast notification.
        notification_recipient = cls.construct_notification_recipient(
            notification=notification, recipient=None
        )
        notification_recipient.save()

        notification_created.send(
            sender=cls,
            notification=notification,
            notification_recipients=[notification_recipient],
            user=sender,
        )

        return notification

    @classmethod
    @baserow_trace(tracer)
    def create_direct_notification_for_users(
        cls,
        notification_type: str,
        recipients: List[AbstractUser],
        sender: Optional[AbstractUser] = None,
        data: Optional[Dict[str, Any]] = None,
        workspace: Optional[Workspace] = None,
        **kwargs,
    ) -> List[NotificationRecipient]:
        """
        Creates a notification for each user in the given list with the provided data.

        :param notification_type: The type of the notification.
        :param recipients: The users that will receive the notification.
        :param data: The data that will be stored in the notification.
        :param workspace: The workspace that the notification is linked to.
        :param kwargs: Any additional kwargs that will be passed to the
            Notification constructor.
        :return: A list of the created notification recipients instances.
        """

        notification = cls.create_notification(
            notification_type=notification_type,
            data=data,
            sender=sender,
            broadcast=False,
            workspace=workspace,
            **kwargs,
        )

        # Prefetch the user profiles if possible to avoid N+1 queries later
        if isinstance(recipients, QuerySet) and issubclass(recipients.model, User):
            recipients = recipients.select_related("profile")

        notification_recipients = NotificationRecipient.objects.bulk_create(
            [
                cls.construct_notification_recipient(
                    recipient=recipient, notification=notification
                )
                for recipient in recipients
            ]
        )

        notification_created.send(
            sender=cls,
            user=sender,
            notification=notification,
            notification_recipients=notification_recipients,
        )
        return notification_recipients

    @classmethod
    @baserow_trace(tracer)
    def construct_email_summary_for_user(
        cls,
        user: AbstractUser,
        notifications: List[Notification],
        total_new_count: int,
    ) -> NotificationsSummaryEmail:
        """
        Constructs an email notification for the given user containing the given
        notifications.

        :param user: The user to construct the email for.
        :param notifications: The notifications to include in the email body.
        :param total_new_count: The total number of new notifications for the
            user.
        :raises ValueError: If no notifications are provided.
        :return: The constructed summary email translated in the user language.
        """

        if not notifications:
            raise ValueError("Provide at least one notification to construct an email.")

        with translation.override(user.profile.language):
            return NotificationsSummaryEmail(
                to=[user.email],
                notifications=notifications,
                new_notifications_count=total_new_count,
            )

    @classmethod
    @baserow_trace(tracer)
    def filter_and_annotate_users_with_notifications_to_send_by_email(
        cls,
        user_filters_q: Q,
        limit_users: Optional[int] = None,
        limit_notifications_per_user: Optional[int] = None,
    ) -> UserWithScheduledEmailNotifications:
        """
        Filters the users based on the provided filters and identifies those who
        have pending email notifications.

        The function also enriches the returned queryset by adding an
        'unsent_email_notifications' attribute to each user. This attribute
        contains the unsent notifications for the user that are scheduled to be
        sent by email. The number of users returned can be limited by providing
        the `limit_users` argument. The default value of None means that no
        limit will be applied.
        The number of notifications per user can also be limited by providing the
        `limit_notifications_per_user` argument. The default value of None means
        that the value of `settings.MAX_NOTIFICATIONS_LISTED_PER_EMAIL` will be
        used.

        :param user_filters_q: A Q object containing the filters to apply to the
            users.
        :param limit_users: The maximum number of users to return.
        :param limit_notifications_per_user: The maximum number of notifications
            to return per user.
        :return: A list of users who meet the provided filters and have unsent
            email notifications and the count of the remaining users to notify
            that are not part of the returned list . Each user instance in the
            list has an additional 'unsent_email_notifications' attribute
            containing their respective unsent notifications.
        """

        if not limit_notifications_per_user:
            limit_notifications_per_user = settings.MAX_NOTIFICATIONS_LISTED_PER_EMAIL

        unsent_notification_subquery = Subquery(
            NotificationRecipient.objects.filter(
                recipient_id=OuterRef("notificationrecipient__recipient_id"),
                **NOTIFICATIONS_WITH_EMAIL_SCHEDULED_FILTERS,
            )
            .order_by("-created_on")
            .values_list("notification_id", flat=True)[:limit_notifications_per_user]
        )

        notifications_to_send_by_email_prefetch = Prefetch(
            "notifications",
            queryset=Notification.objects.filter(
                id__in=unsent_notification_subquery
            ).distinct(),
            to_attr="unsent_email_notifications",
        )

        filtered_users = User.objects.filter(
            user_filters_q,
            **{
                f"notificationrecipient__{k}": v
                for k, v in NOTIFICATIONS_WITH_EMAIL_SCHEDULED_FILTERS.items()
            },
        ).distinct()

        users_with_unsent_notifications = (
            filtered_users.annotate(total_unsent_count=Count("notificationrecipient"))
            .select_related("profile")
            .prefetch_related(notifications_to_send_by_email_prefetch)
        )

        remaining_users_to_notify_count = 0
        if limit_users:
            remaining_users_to_notify_count = max(
                filtered_users.count() - limit_users, 0
            )

        return UserWithScheduledEmailNotifications(
            list(users_with_unsent_notifications[:limit_users]),
            remaining_users_to_notify_count,
        )

    @classmethod
    @baserow_trace(tracer)
    def mark_all_notifications_matching_filters_as_sent_by_emails(
        cls, filters_q: Q
    ) -> int:
        """
        Marks all notification recipients as sent by email for all users
        matching the provided filters.

        :param filters_q: A Q object containing the filters to apply to the
            notification recipient objects.
        :return The number of notification recipients marked as sent.
        """

        return NotificationRecipient.objects.filter(
            filters_q, email_scheduled=True
        ).update(email_scheduled=False)

    @classmethod
    @baserow_trace(tracer)
    def send_unread_notifications_by_email_to_users_matching_filters(
        cls, user_filters_q: Q, max_emails: Optional[int] = None
    ) -> UserWithScheduledEmailNotifications:
        """
        Sends new notifications by email to all users matching the provided
        filters, up to the provided maximum number of emails.

        :param user_filters_q: A Q object containing the filters to apply to the
            users.
        :param max_emails: The maximum number of emails to send. If 0 or None,
            all emails will be sent.
        :return: An UserWithScheduledEmailNotifications object containing a list
            of users with notifications scheduled to be sent by email and the
            count of the remaining users to notify that are not part of the
            returned list.
        """

        result = cls.filter_and_annotate_users_with_notifications_to_send_by_email(
            user_filters_q, max_emails
        )

        emails: List[NotificationsSummaryEmail] = []
        email_recipient_ids: List[int] = []

        # The greatest notification ID is used to determine the last notification
        # fetched in the previous query and to avoid later marking as sent any
        # notifications that were created between select and later update.
        greatest_notification_id = 0

        for user in result.users_with_notifications:
            email = cls.construct_email_summary_for_user(
                user, user.unsent_email_notifications, user.total_unsent_count
            )

            emails.append(email)
            email_recipient_ids.append(user.id)
            greatest_notification_id = max(
                greatest_notification_id, user.unsent_email_notifications[0].id
            )
            logger.debug(
                f"Prepared a notifications summary email for {user.email} ({user.id}) "
                f"with {len(user.unsent_email_notifications)} notifications."
            )

        if emails:
            with atomic_if_not_already():
                cls.mark_all_notifications_matching_filters_as_sent_by_emails(
                    Q(
                        recipient_id__in=email_recipient_ids,
                        notification_id__lte=greatest_notification_id,
                    )
                )

                UserProfile.objects.filter(user_id__in=email_recipient_ids).update(
                    last_notifications_email_sent_at=datetime.now(tz=timezone.utc)
                )

                if settings.EMAIL_NOTIFICATIONS_ENABLED:
                    logger.debug(
                        f"Successfully queued {len(emails)} emails for sending."
                    )

                    transaction.on_commit(
                        lambda: get_mail_connection(fail_silently=False).send_messages(
                            emails
                        )
                    )

        return result


class UserNotificationsGrouper:
    """
    A utility class that aggregates notifications per user, enabling a single
    message delivery containing all the user's relevant notifications, rather
    than sending each notification individually.
    """

    def __init__(self):
        self.notifications: List[Notification] = []
        self.recipients_ids: List[List[int]] = []
        self.user_ids = set()

    def has_notifications_to_send(self):
        return len(self.notifications) > 0

    def add(self, notification: Notification, recipient_ids: List[int]):
        self.user_ids |= set(recipient_ids)
        self.recipients_ids.append(recipient_ids)
        self.notifications.append(notification)

    def create_all_notifications_and_trigger_task(self, batch_size=2500):
        all_recipients = {
            u.id: u
            for u in User.objects.filter(id__in=self.user_ids).select_related("profile")
        }

        created_notifications = Notification.objects.bulk_create(
            self.notifications, batch_size=batch_size
        )

        notification_recipients = []
        for i, notification in enumerate(created_notifications):
            notification_recipients.extend(
                [
                    NotificationHandler.construct_notification_recipient(
                        notification=notification,
                        recipient=all_recipients[recipient_id],
                        queued=True,
                    )
                    for recipient_id in self.recipients_ids[i]
                ]
            )

        NotificationRecipient.objects.bulk_create(
            notification_recipients, batch_size=batch_size, ignore_conflicts=True
        )
        logger.debug(
            "Queued %s notifications ready to be grouped and sent to %s different users",
            len(created_notifications),
            len(self.user_ids),
        )
        transaction_on_commit_if_not_already(send_queued_notifications_to_users.delay)

    def user_grouper(self):
        while True:
            notification, recipients = yield
            self.add(notification, recipients)

    def __enter__(self):
        self.user_grouper = self.user_grouper()
        next(self.user_grouper)
        return self.user_grouper

    def __exit__(self, exc_type, exc_value, traceback):
        self.user_grouper.close()
        if exc_type is None:
            self.create_all_notifications_and_trigger_task()
