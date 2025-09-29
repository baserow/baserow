import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import chain, groupby
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from django.utils.translation import gettext as _

from baserow.contrib.database.fields.field_types import (
    LongTextFieldType,
    MultipleCollaboratorsFieldType,
)
from baserow.contrib.database.rows.handler import RowM2MChangeTracker
from baserow.contrib.database.rows.signals import rows_created, rows_updated
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.core.notifications.handler import (
    NotificationHandler,
    UserNotificationsGrouper,
)
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.table.models import GeneratedTableModel


@dataclass
class CollaboratorAddedToRowNotificationData:
    database_id: int
    database_name: str
    table_id: int
    table_name: str
    field_id: int
    field_name: str
    row_id: int
    row_name: str


class CollaboratorAddedToRowNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "collaborator_added_to_row"
    has_web_frontend_route = True

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(sender)s assigned you to %(field_name)s in row %(row_name)s in %(table_name)s."
        ) % {
            "sender": notification.sender.first_name
            if notification.sender
            else _("An unknown user"),
            "field_name": notification.data["field_name"],
            "row_name": notification.data.get("row_name", notification.data["row_id"]),
            "table_name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return None

    @classmethod
    def construct_notification(
        cls, sender: AbstractUser, row: "GeneratedTableModel", field: "Field"
    ):
        """
        Notifies the given users that they have been added to the given row.

        :param sender: The user that added the given users to the row.
        :param row: The row that the users have been added to.
        :param field: The field that the users have been added to.
        """

        table = row.baserow_table
        workspace = table.database.workspace
        data = CollaboratorAddedToRowNotificationData(
            row_id=row.id,
            row_name=str(row),
            field_id=field.id,
            field_name=field.name,
            table_id=table.id,
            table_name=table.name,
            database_id=table.database.id,
            database_name=table.database.name,
        )

        return NotificationHandler.construct_notification(
            cls.type, data=asdict(data), sender=sender, workspace=workspace
        )

    @classmethod
    def _iter_field_row_and_collaborators_to_notify(
        cls,
        m2m_change_tracker: RowM2MChangeTracker,
        updated_rows: List["GeneratedTableModel"],
    ) -> List[Tuple["Field", "GeneratedTableModel", List[AbstractUser]]]:
        # The row provided by the iterator might not have all the updated values in
        # case of a bulk row update. This is because some fields require a returning
        # value after insert or update, but the `bulk_update` in the `create_rows`
        # method doesn't update these computed properties, so this row might have a
        # raw expression instead of the computed output. We're therefore replacing the
        # row from the updated set.
        row_id_map = {row.id: row for row in updated_rows}

        field_rows_and_collaborators_to_notify = {
            field: row_and_collaborators_to_notify
            for field, row_and_collaborators_to_notify in m2m_change_tracker.get_created_m2m_rels_per_field_for_type(
                MultipleCollaboratorsFieldType.type
            ).items()
            if field.notify_user_when_added
        }

        return chain.from_iterable(
            (
                (field, row_id_map[row.id], collaborators_to_notify)
                for row, collaborators_to_notify in row_and_collaborators_to_notify.items()
                if collaborators_to_notify
            )
            for field, row_and_collaborators_to_notify in field_rows_and_collaborators_to_notify.items()
        )

    @classmethod
    def create_notifications_grouped_by_user(
        cls,
        user: AbstractUser,
        m2m_change_tracker: RowM2MChangeTracker,
        rows: List["GeneratedTableModel"],
    ):
        """
        Creates notifications grouped by user for the given rows and
        collaborator fields. It uses the UserNotificationsGrouper to group the
        notifications by user and trigger the task to send the notifications
        for each user at the end.

        :param user: The user that added the given users to the row.
        :param m2m_change_tracker: A change tracker containing all changes to m2m
            relationships that just occurred, so we can create any needed notification.
        :param rows: A list containing all the updated rows in the latest version.
            The ones in the m2m_change_tracker might not be up-to-date because the
            `bulk_update` function from Django doesn't get return the computed values.
        """

        notification_grouper = UserNotificationsGrouper()

        iterator = cls._iter_field_row_and_collaborators_to_notify(
            m2m_change_tracker, rows
        )
        for field, row, user_ids_to_notify in iterator:
            notification = cls.construct_notification(sender=user, row=row, field=field)
            notification_grouper.add(notification, list(user_ids_to_notify))

        if notification_grouper.has_notifications_to_send():
            notification_grouper.create_all_notifications_and_trigger_task()


@dataclass
class UserMentionInRichTextFieldNotificationData:
    database_id: int
    database_name: str
    table_id: int
    table_name: str
    field_id: int
    field_name: str
    row_id: int
    row_name: str


# TODO: Make the link in the email notification clickable
class UserMentionInRichTextFieldNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "user_mention_in_rich_text_field"
    has_web_frontend_route = True

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(sender)s mentioned you in %(field_name)s in row %(row_name)s in %(table_name)s."
        ) % {
            "sender": notification.sender.first_name,
            "field_name": notification.data["field_name"],
            "row_name": notification.data.get("row_name", notification.data["row_id"]),
            "table_name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return notification.data.get("field_content")

    @classmethod
    def construct_notification(
        cls, sender: AbstractUser, row: "GeneratedTableModel", field: "Field"
    ):
        """
        Notifies the given users that they have been mentioned into the given row.

        :param sender: The user that mentioned the given users to the row.
        :param row: The row that the users have been mentioned to.
        :param field: The field that the users have been mentioned to.
        """

        table = row.baserow_table
        workspace = table.database.workspace
        data = UserMentionInRichTextFieldNotificationData(
            row_id=row.id,
            row_name=str(row),
            field_name=field.name,
            field_id=field.id,
            table_id=table.id,
            table_name=table.name,
            database_id=table.database.id,
            database_name=table.database.name,
        )

        return NotificationHandler.construct_notification(
            cls.type, data=asdict(data), sender=sender, workspace=workspace
        )

    @classmethod
    def _iter_field_row_and_users_to_notify(
        cls,
        rows: List["GeneratedTableModel"],
        updated_field_ids: Optional[List[int]] = None,
    ) -> Iterable[Tuple["Field", "GeneratedTableModel", List[AbstractUser]]]:
        row_id_map = {row.id: row for row in rows}

        if not rows:
            return

        model = rows[0]._meta.model
        table = model.baserow_table

        workspace_user_ids = set(
            table.database.workspace.users.values_list("id", flat=True)
        )

        rich_text_fields_updated = [
            fo
            for fo in model.get_field_objects()
            if isinstance(fo["type"], LongTextFieldType)
            and fo["field"].long_text_enable_rich_text
            and (updated_field_ids is None or fo["field"].id in updated_field_ids)
        ]
        if not rich_text_fields_updated:
            return

        rich_text_mentions = []
        mentions_keys_set = set()

        # Define a function to get a unique key for a mention object. This key is used
        # to distinguish between the mentions that already exist and the ones that were
        # created.
        def get_key(obj):
            return f"{obj.field_id}:{obj.row_id}:{obj.user_id}"

        for field_obj in rich_text_fields_updated:
            field = field_obj["field"]
            field_name = field_obj["name"]
            for row in rows:
                content = getattr(row, field_name)
                if not content:
                    continue

                # Look for valid user id mentions in the content that are actually
                # users of the workspace
                mentioned_user_ids = set(map(int, re.findall(r"@(\d+)", content)))
                mentioned_user_ids_in_workspace = (
                    workspace_user_ids & mentioned_user_ids
                )

                for user_id in mentioned_user_ids_in_workspace:
                    mention_obj = RichTextFieldMention(
                        table=table, field=field, row_id=row.id, user_id=user_id
                    )
                    rich_text_mentions.append(mention_obj)
                    mentions_keys_set.add(get_key(mention_obj))

        # Find out which mentions need to be deleted and which ones already exist
        prev_mentions = (
            RichTextFieldMention.objects.filter(
                table=table,
                field__in=[fo["field"] for fo in rich_text_fields_updated],
                row_id__in=row_id_map.keys(),
            )
            .select_for_update(of=("self",))
            .order_by("id")  # Specific order to avoid deadlocks
        )
        existing_mention_ids_to_delete = set()
        existing_mention_keys_to_keep = set()
        for mention in prev_mentions:
            key = get_key(mention)
            if key in mentions_keys_set:
                existing_mention_keys_to_keep.add(key)
            else:
                existing_mention_ids_to_delete.add(mention.id)

        # Using ignore_conflicts=True prevents errors when a mention already exists.
        # However, it returns all the provided mentions with None as the ID. We use
        # existing_mention_keys_to_keep to differentiate between pre-existing and newly
        # created mentions.
        if rich_text_mentions:
            created_or_updated_mentions = RichTextFieldMention.objects.bulk_create(
                rich_text_mentions,
                update_conflicts=True,
                update_fields=["marked_for_deletion_at"],
                unique_fields=["table", "field", "row_id", "user"],
            )
            created_mentions = [
                obj
                for obj in created_or_updated_mentions
                if get_key(obj) not in existing_mention_keys_to_keep
            ]
            for (field, row_id), group in groupby(
                created_mentions, lambda m: (m.field, m.row_id)
            ):
                yield field, row_id_map[row_id], [mention.user_id for mention in group]

        # Mark invalid mentions for deletion. They're kept in the database temporarily
        # to prevent duplicate notifications if changes are quickly undone/redone or
        # mentions are quickly removed/re-added.
        # See STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES for more info.
        if existing_mention_ids_to_delete:
            RichTextFieldMention.objects.filter(
                id__in=existing_mention_ids_to_delete
            ).update(marked_for_deletion_at=datetime.now(tz=timezone.utc))

    @classmethod
    def create_notifications_grouped_by_user(
        cls,
        user: AbstractUser,
        rows: List["GeneratedTableModel"],
        updated_field_ids: Optional[List[int]] = None,
    ):
        """
        Creates notifications grouped by user for the given rows when the user has been
        mentioned in a rich text field. It uses the UserNotificationsGrouper to group
        the notifications by user and trigger the task to send the notifications for
        each user at the end.

        :param user: The user that edited the rows.
        :param rows: A list containing all the updated rows in the latest version. The
            ones in the m2m_change_tracker might not be up-to-date because the
            `bulk_update` function from Django doesn't get return the computed values.
        :param updated_field_ids: A list containing all the field ids for the updated
            fields.
        """

        notification_grouper = UserNotificationsGrouper()

        iterator = cls._iter_field_row_and_users_to_notify(rows, updated_field_ids)
        for field, row, user_ids_to_notify in iterator:
            notification = cls.construct_notification(sender=user, row=row, field=field)
            notification_grouper.add(notification, list(user_ids_to_notify))

        if notification_grouper.has_notifications_to_send():
            notification_grouper.create_all_notifications_and_trigger_task()


@receiver(rows_created)
def notify_users_when_rows_created(
    sender,
    rows,
    before,
    user,
    table,
    model,
    send_realtime_update=True,
    send_webhook_events=True,
    m2m_change_tracker=None,
    **kwargs,
):
    if m2m_change_tracker is not None:
        CollaboratorAddedToRowNotificationType.create_notifications_grouped_by_user(
            user, m2m_change_tracker, rows
        )

    UserMentionInRichTextFieldNotificationType.create_notifications_grouped_by_user(
        user, rows
    )


@receiver(rows_updated)
def notify_users_when_rows_updated(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    updated_field_ids,
    m2m_change_tracker=None,
    **kwargs,
):
    if m2m_change_tracker is not None:
        CollaboratorAddedToRowNotificationType.create_notifications_grouped_by_user(
            user, m2m_change_tracker, rows
        )

    UserMentionInRichTextFieldNotificationType.create_notifications_grouped_by_user(
        user, rows, updated_field_ids
    )
