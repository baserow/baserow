from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.handler import CoreHandler
from baserow.core.prosemirror.utils import (
    extract_mentioned_users_in_workspace,
    is_valid_prosemirror_document,
)
from baserow.core.trash.handler import TrashHandler
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.row_comments.exceptions import (
    InvalidRowCommentException,
    InvalidRowCommentMentionException,
    InvalidRowsCommentNotificationModeException,
    RowCommentDoesNotExist,
    UserNotRowCommentAuthorException,
)
from baserow_premium.row_comments.models import (
    ALL_ROW_COMMENT_NOTIFICATION_MODES,
    RowComment,
    RowCommentsNotificationMode,
    RowCommentsNotificationModes,
)
from baserow_premium.row_comments.operations import (
    CreateRowCommentsOperationType,
    DeleteRowCommentsOperationType,
    ReadRowCommentsOperationType,
    UpdateRowCommentsOperationType,
)
from baserow_premium.row_comments.signals import (
    row_comment_created,
    row_comment_deleted,
    row_comment_updated,
    row_comments_notification_mode_updated,
)


class RowCommentHandler:
    @classmethod
    def get_comments(
        cls,
        requesting_user: AbstractUser,
        table_id: int,
        row_id: int,
        include_trash: bool = False,
    ) -> QuerySet:
        """
        Returns all the row comments for a given row in a table.

        :param requesting_user: The user who is requesting to lookup the row comments.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to get comments for.
        :param include_trash: If True, trashed comments will be included in the
            queryset.
        :return: A queryset of all row comments for that particular row.
        :raises TableDoesNotExist: If the table does not exist.
        :raises RowDoesNotExist: If the row does not exist.
        :raises UserNotInWorkspace: If the user is not a member of the workspace that
            the table is in.
        """

        table = TableHandler().get_table(table_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, requesting_user, table.database.workspace
        )
        # TODO: RBAC -> When row level permissions are introduced we also need to check
        #       that the user can see the row
        CoreHandler().check_permissions(
            requesting_user,
            ReadRowCommentsOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        RowHandler().has_row(requesting_user, table, row_id, raise_error=True)

        row_comment_manager = RowComment.objects
        if include_trash:
            row_comment_manager = RowComment.objects_and_trash

        return (
            row_comment_manager.select_related("user")
            .filter(table_id=table_id, row_id=row_id)
            .all()
        )

    @classmethod
    def get_comment_by_id(
        cls, requesting_user: AbstractUser, table_id: int, comment_id: int
    ) -> RowComment:
        """
        Returns the row comment for a given comment id.

        :param requesting_user: The user who is requesting to lookup the row
            comments.
        :param table_id: The table to find the row in.
        :param comment_id: The id of the comment to get.
        :return: the comment for that particular row.
        :raises PermissionException: If the user does not have permission to
            read comment on the table.
        :raises RowCommentDoesNotExist: If the comment does not exist.
        """

        table = TableHandler().get_table(table_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, requesting_user, table.database.workspace
        )

        # TODO: RBAC -> When row level permissions are introduced we also need
        #       to check that the user can see the row
        CoreHandler().check_permissions(
            requesting_user,
            ReadRowCommentsOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        queryset = RowComment.objects.select_related(
            "table__database__workspace"
        ).prefetch_related("mentions")

        try:
            row_comment = queryset.get(pk=comment_id)
            RowHandler().has_row(
                requesting_user, table, row_comment.row_id, raise_error=True
            )
        except (RowComment.DoesNotExist, RowDoesNotExist):
            raise RowCommentDoesNotExist()

        return row_comment

    @classmethod
    def create_comment(
        cls,
        requesting_user: AbstractUser,
        table_id: int,
        row_id: int,
        message: Dict[str, Any],
    ) -> RowComment:
        """
        Creates a new row comment on the specified row.

        :param requesting_user: The user who is making the comment.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to post the comment on.
        :param message: The comment content to post. It must be a dict
            containing a valid prosemirror document.
        :return: The newly created RowComment instance.
        :raises TableDoesNotExist: If the table does not exist.
        :raises RowDoesNotExist: If the row does not exist.
        :raises UserNotInWorkspace: If the user is not a member of the workspace
            that the table is in.
        :raises InvalidRowCommentException: If the comment content is not a
            valid prosemirror doc.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, requesting_user, workspace
        )

        # TODO: RBAC -> When row level permissions are introduced we also need to check
        #       that the user can see the row
        CoreHandler().check_permissions(
            requesting_user,
            CreateRowCommentsOperationType.type,
            workspace=workspace,
            context=table,
        )

        row = RowHandler().get_row(requesting_user, table, row_id)

        if not is_valid_prosemirror_document(message):
            raise InvalidRowCommentException()

        try:
            mentions = extract_mentioned_users_in_workspace(message, workspace)
        except ValueError:
            raise InvalidRowCommentMentionException()

        row_comment = RowComment.objects.create(
            user=requesting_user,
            table=table,
            row_id=row_id,
            message=message,
            comment=message,
        )

        if mentions:
            row_comment.mentions.set(mentions)

        row_comment_created.send(
            cls,
            row_comment=row_comment,
            row=row,
            user=requesting_user,
            mentions=list(mentions),
        )
        return row_comment

    @classmethod
    def update_comment(
        cls,
        requesting_user: AbstractUser,
        row_comment: RowComment,
        message: Dict[str, Any],
    ) -> RowComment:
        """
        Updates a new row comment on the specified row.

        :param requesting_user: The user who is making the comment.
        :param row_comment: The comment content for the update.
        :param message: The new content of the comment.
        :return: The updated RowComment instance.
        :raises PermissionException: If the user does not have permission to delete
            the comment.
        :raises UserNotRowCommentAuthorException: If the user is not the author of the
            comment.
        :raises InvalidRowCommentException: If the comment is blank or None.
        """

        table = row_comment.table
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            requesting_user,
            UpdateRowCommentsOperationType.type,
            workspace=workspace,
            context=table,
        )

        # only the owner of the comment can update it
        if row_comment.user_id != requesting_user.id:
            raise UserNotRowCommentAuthorException()

        if not is_valid_prosemirror_document(message):
            raise InvalidRowCommentException()

        try:
            new_mentions = extract_mentioned_users_in_workspace(message, workspace)
            old_mentions = row_comment.mentions.all()
        except ValueError:
            raise InvalidRowCommentMentionException()

        row_comment.message = message
        row_comment.save(update_fields=["message", "updated_on"])

        if new_mentions:
            row_comment.mentions.set(new_mentions)

        row = RowHandler().get_row(requesting_user, table, row_comment.row_id)

        row_comment_updated.send(
            cls,
            row_comment=row_comment,
            row=row,
            user=requesting_user,
            mentions=list(set(new_mentions) - set(old_mentions)),
        )
        return row_comment

    @classmethod
    def delete_comment(cls, requesting_user: AbstractUser, row_comment: RowComment):
        """
        Set a row comment marked as trashed and so it will not be visible to
        users anymore.

        :param requesting_user: The user who is making the comment.
        :param row_comment: The comment to delete.
        :raises PermissionException: If the user does not have permission to delete
            the comment.
        :raises UserNotRowCommentAuthorException: If the user is not the author of the
            comment.
        """

        table = row_comment.table
        database = table.database
        CoreHandler().check_permissions(
            requesting_user,
            DeleteRowCommentsOperationType.type,
            workspace=database.workspace,
            context=table,
        )

        # only the owner of the comment can trash it
        if row_comment.user_id != requesting_user.id:
            raise UserNotRowCommentAuthorException()

        TrashHandler.trash(requesting_user, database.workspace, database, row_comment)

        mentions = list(row_comment.mentions.all())
        row_comment_deleted.send(
            cls,
            row_comment=row_comment,
            user=requesting_user,
            mentions=mentions,
        )

    @classmethod
    def get_users_to_notify_for_comment(
        cls, row_comment: RowComment, user_ids_to_exclude=None
    ) -> List[AbstractUser]:
        """
        Returns a list of users who should be notified about a new comment on a
        table row. This list will not include the sender of the comment.

        :param row_comment: The comment to notify users about.
        :param user_ids_to_exclude: A list of user ids to exclude from the
            returned list (i.e. users mentioned in the comment).
        :return: A queryset of users who should be notified about the comment.
        """

        user_ids_to_exclude = user_ids_to_exclude or []
        users_to_notify = []

        # select related the user__profile because we'll need it later to get
        # the user's notification frequency preference. Since the
        # `check_permission_for_multiple_actors` will return a list of users,
        # the NotificationHandler cannot select_related the user__profile for us
        # later on.
        user_subscriptions = (
            RowCommentsNotificationMode.objects.exclude(
                user_id__in=[*user_ids_to_exclude, row_comment.user_id]
            )
            .filter(
                table_id=row_comment.table_id,
                row_id=row_comment.row_id,
                mode=RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
            )
            .select_related("user__profile")
        )

        if len(user_subscriptions):
            # Ensure users can see comments for this table
            users_to_notify = CoreHandler().check_permission_for_multiple_actors(
                [u.user for u in user_subscriptions],
                ReadRowCommentsOperationType.type,
                workspace=row_comment.table.database.workspace,
                context=row_comment.table,
            )

        return users_to_notify

    @classmethod
    def update_row_comments_notification_mode(
        cls,
        user: AbstractUser,
        table_id: int,
        row_id: int,
        mode: RowCommentsNotificationModes,
        include_user_in_signal=False,
    ):
        """
        Updates the user's notification settings for comments on a specific
        table row. It either creates a database entry to notify the user about
        all comments on that row, or deletes the entry if the user prefers
        notifications only when mentioned. In this last case, the proper
        notification_type will take care to send the notification to the
        mentioned user.

        :param requesting_user: The user who is subscribing to the row's
            comments.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to subscribe to.
        :param mode: The subscription mode.
        :param include_user_in_signal: If True, the user sessions will be
            included in the signal that is sent.
        :raises TableDoesNotExist: If the table does not exist.
        :raises RowDoesNotExist: If the row does not exist.
        :raises UserNotInWorkspace: If the user is not a member of the workspace
            that the table is in.
        :raises InvalidRowCommentSubscriptionModeException: If the subscription
            mode is invalid.
        """

        if mode not in ALL_ROW_COMMENT_NOTIFICATION_MODES:
            raise InvalidRowsCommentNotificationModeException(
                "Invalid subscription mode."
            )

        # ensure the table and row exist and user has access to them
        table = TableHandler().get_table(table_id)
        row = RowHandler().get_row(user, table, row_id)

        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user, table.database.workspace
        )

        CoreHandler().check_permissions(
            user,
            ReadRowCommentsOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        RowCommentsNotificationMode.objects.update_or_create(
            table=table, row_id=row_id, user=user, defaults={"mode": mode}
        )

        row_comments_notification_mode_updated.send(
            cls,
            user=user,
            table=table,
            row_id=row.id,
            mode=mode,
            include_user_in_signal=include_user_in_signal,
        )
