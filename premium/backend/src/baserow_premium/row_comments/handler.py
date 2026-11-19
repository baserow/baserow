from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch, Q, QuerySet

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.operations import (
    CreateViewRowCommentOperationType,
    DeleteViewRowCommentOperationType,
    ReadViewRowCommentsOperationType,
    UpdateViewRowCommentOperationType,
)
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
)
from baserow.contrib.database.views.utils import check_permissions_with_view_fallback
from baserow.core.handler import CoreHandler
from baserow.core.models import User, Workspace
from baserow.core.prosemirror.utils import (
    extract_mentioned_users_in_workspace,
    is_valid_prosemirror_document,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.types import PermissionCheck
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

ROW_COMMENT_SEARCH_OPERATIONS = (
    ReadRowCommentsOperationType.type,
    ReadDatabaseRowOperationType.type,
)


def _get_view_if_provided(user, view_id):
    """
    Resolves an optional view_id to a View instance.
    """

    if view_id is None:
        return None

    return ViewHandler().get_view_as_user(user, view_id)


class RowCommentSearchResult(NamedTuple):
    comments: List[RowComment]
    has_more: bool


class RowCommentHandler:
    @classmethod
    def get_comments(
        cls,
        requesting_user: AbstractUser,
        table_id: int,
        row_id: int,
        include_trash: bool = False,
        view_id: Optional[int] = None,
    ) -> QuerySet:
        """
        Returns all the row comments for a given row in a table.

        :param requesting_user: The user who is requesting to lookup the row comments.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to get comments for.
        :param include_trash: If True, trashed comments will be included in the
            queryset.
        :param view_id: Optionally provide a view id. If the user doesn't have
            table-level permissions, view-level permissions will be checked as
            a fallback.
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

        view = _get_view_if_provided(requesting_user, view_id)
        check_permissions_with_view_fallback(
            ReadRowCommentsOperationType.type,
            ReadViewRowCommentsOperationType.type,
            requesting_user,
            table,
            view,
            row_ids=[row_id],
        )

        RowHandler().has_row(
            requesting_user, table, row_id, raise_error=True, view=view
        )

        row_comment_manager = RowComment.objects
        if include_trash:
            row_comment_manager = RowComment.objects_and_trash

        return (
            row_comment_manager.select_related("user__profile")
            .filter(table_id=table_id, row_id=row_id)
            .all()
        )

    @classmethod
    def get_comment_by_id(
        cls,
        requesting_user: AbstractUser,
        table_id: int,
        comment_id: int,
        view_id: Optional[int] = None,
    ) -> RowComment:
        """
        Returns the row comment for a given comment id.

        :param requesting_user: The user who is requesting to lookup the row
            comments.
        :param table_id: The table to find the row in.
        :param comment_id: The id of the comment to get.
        :param view_id: Optionally provide a view id for permission fallback.
        :return: the comment for that particular row.
        :raises PermissionException: If the user does not have permission to
            read comment on the table.
        :raises RowCommentDoesNotExist: If the comment does not exist.
        """

        table = TableHandler().get_table(table_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, requesting_user, table.database.workspace
        )

        queryset = RowComment.objects.select_related(
            "table__database__workspace", "user__profile"
        ).prefetch_related(
            Prefetch("mentions", queryset=User.objects_and_identities.all())
        )

        try:
            row_comment = queryset.get(pk=comment_id)
        except RowComment.DoesNotExist:
            raise RowCommentDoesNotExist()

        view = _get_view_if_provided(requesting_user, view_id)
        check_permissions_with_view_fallback(
            ReadRowCommentsOperationType.type,
            ReadViewRowCommentsOperationType.type,
            requesting_user,
            table,
            view,
            row_ids=[row_comment.row_id],
        )

        if not RowHandler().has_row(
            requesting_user, table, row_comment.row_id, view=view
        ):
            raise RowCommentDoesNotExist()

        return row_comment

    @classmethod
    def search_comments(
        cls,
        requesting_user: AbstractUser,
        workspace: Workspace,
        tables: List[Table],
        mentioned_user_ids: Optional[List[int]] = None,
        author_ids: Optional[List[int]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> RowCommentSearchResult:
        """
        Returns the newest comments on the rows of the given tables. A search for
        mentions starts from the mentions of those users. Any other search reads
        every table newest first on its own, up to the page asked for.

        :param requesting_user: The user who is searching the comments.
        :param workspace: The workspace of the tables.
        :param tables: The tables whose comments are searched.
        :param mentioned_user_ids: If provided, only the comments mentioning one of
            these users are returned.
        :param author_ids: If provided, only the comments written by one of these
            users are returned.
        :param created_after: If provided, only the comments created at or after
            this moment are returned.
        :param created_before: If provided, only the comments created before this
            moment are returned.
        :param limit: The most comments to return.
        :param offset: How many of the newest matching comments to skip.
        :return: The comments, newest first, with their author and mentions, and
            whether more candidates matched before checking which rows still exist.
        :raises FeaturesNotAvailableError: If the user doesn't have the premium
            feature in the workspace.
        :raises PermissionException: If the user may not read the comments of one
            of the tables.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, requesting_user, workspace
        )
        CoreHandler().check_multiple_permissions(
            [
                PermissionCheck(requesting_user, operation, table)
                for table in tables
                for operation in ROW_COMMENT_SEARCH_OPERATIONS
            ],
            workspace=workspace,
            raise_exception=True,
        )

        if not tables:
            return RowCommentSearchResult([], False)

        filters = Q()
        if author_ids is not None:
            filters &= Q(user_id__in=author_ids)
        if created_after is not None:
            filters &= Q(created_on__gte=created_after)
        if created_before is not None:
            filters &= Q(created_on__lt=created_before)
        newest = (
            RowComment.objects.filter(filters)
            .order_by("-created_on", "-id")
            .values("id", "created_on")
        )
        if mentioned_user_ids is not None:
            # One query over the tables lets the database start from the mentions.
            newest = newest.filter(
                id__in=RowComment.mentions.through.objects.filter(
                    user_id__in=mentioned_user_ids
                ).values("rowcomment_id"),
                table_id__in=[table.id for table in tables],
            )
        else:
            per_table = [
                newest.filter(table_id=table.id)[: offset + limit + 1]
                for table in tables
            ]
            newest = per_table[0]
            if len(per_table) > 1:
                newest = newest.union(*per_table[1:], all=True).order_by(
                    "-created_on", "-id"
                )
        comment_ids = [comment["id"] for comment in newest[offset : offset + limit + 1]]

        comments = list(
            RowComment.objects.filter(id__in=comment_ids[:limit])
            .order_by("-created_on", "-id")
            .select_related("user")
            .prefetch_related(
                Prefetch("mentions", queryset=User.objects_and_identities.all())
            )
        )
        return RowCommentSearchResult(
            cls._on_existing_rows(tables, comments), len(comment_ids) > limit
        )

    @classmethod
    def _on_existing_rows(
        cls, tables: List[Table], comments: List[RowComment]
    ) -> List[RowComment]:
        """
        Leaves out the comments whose row is trashed, with one query per table the
        comments are in.

        :param tables: The tables the comments were searched in.
        :param comments: The comments found.
        :return: The comments on rows that exist, in the given order.
        """

        row_ids = defaultdict(set)
        for comment in comments:
            row_ids[comment.table_id].add(comment.row_id)
        existing = {
            (table.id, row_id)
            for table in tables
            if table.id in row_ids
            # A model without fields costs no query to build.
            for row_id in table.get_model(field_ids=[], add_dependencies=False)
            .objects.filter(id__in=row_ids[table.id])
            .values_list("id", flat=True)
        }
        return [
            comment
            for comment in comments
            if (comment.table_id, comment.row_id) in existing
        ]

    @classmethod
    def create_comment(
        cls,
        requesting_user: AbstractUser,
        table_id: int,
        row_id: int,
        message: Dict[str, Any],
        view_id: Optional[int] = None,
    ) -> RowComment:
        """
        Creates a new row comment on the specified row.

        :param requesting_user: The user who is making the comment.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to post the comment on.
        :param message: The comment content to post. It must be a dict
            containing a valid prosemirror document.
        :param view_id: Optionally provide a view id for permission fallback.
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

        view = _get_view_if_provided(requesting_user, view_id)
        check_permissions_with_view_fallback(
            CreateRowCommentsOperationType.type,
            CreateViewRowCommentOperationType.type,
            requesting_user,
            table,
            view,
            row_ids=[row_id],
        )
        row = RowHandler().get_row(requesting_user, table, row_id, view=view)

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
            row_comment.mentions(manager="objects_and_identities").set(mentions)

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
        view_id: Optional[int] = None,
    ) -> RowComment:
        """
        Updates a new row comment on the specified row.

        :param requesting_user: The user who is making the comment.
        :param row_comment: The comment content for the update.
        :param message: The new content of the comment.
        :param view_id: Optionally provide a view id for permission fallback.
        :return: The updated RowComment instance.
        :raises PermissionException: If the user does not have permission to delete
            the comment.
        :raises UserNotRowCommentAuthorException: If the user is not the author of the
            comment.
        :raises InvalidRowCommentException: If the comment is blank or None.
        """

        table = row_comment.table
        workspace = table.database.workspace

        view = _get_view_if_provided(requesting_user, view_id)
        check_permissions_with_view_fallback(
            UpdateRowCommentsOperationType.type,
            UpdateViewRowCommentOperationType.type,
            requesting_user,
            table,
            view,
            row_ids=[row_comment.row_id],
        )

        # only the owner of the comment can update it
        if row_comment.user_id != requesting_user.id:
            raise UserNotRowCommentAuthorException()

        if not is_valid_prosemirror_document(message):
            raise InvalidRowCommentException()

        try:
            new_mentions = extract_mentioned_users_in_workspace(message, workspace)
            old_mentions = set(
                row_comment.mentions(manager="objects_and_identities").all()
            )
        except ValueError:
            raise InvalidRowCommentMentionException()

        row_comment.message = message
        row_comment.save(update_fields=["message", "updated_on"])

        row_comment.mentions(manager="objects_and_identities").set(new_mentions)

        row = RowHandler().get_row(
            requesting_user, table, row_comment.row_id, view=view
        )

        row_comment_updated.send(
            cls,
            row_comment=row_comment,
            row=row,
            user=requesting_user,
            mentions=list(set(new_mentions) - set(old_mentions)),
        )
        return row_comment

    @classmethod
    def delete_comment(
        cls,
        requesting_user: AbstractUser,
        row_comment: RowComment,
        view_id: Optional[int] = None,
    ):
        """
        Set a row comment marked as trashed and so it will not be visible to
        users anymore.

        :param requesting_user: The user who is making the comment.
        :param row_comment: The comment to delete.
        :param view_id: Optionally provide a view id for permission fallback.
        :raises PermissionException: If the user does not have permission to delete
            the comment.
        :raises UserNotRowCommentAuthorException: If the user is not the author of the
            comment.
        """

        table = row_comment.table
        database = table.database

        view = _get_view_if_provided(requesting_user, view_id)
        check_permissions_with_view_fallback(
            DeleteRowCommentsOperationType.type,
            DeleteViewRowCommentOperationType.type,
            requesting_user,
            table,
            view,
            row_ids=[row_comment.row_id],
        )

        # only the owner of the comment can trash it
        if row_comment.user_id != requesting_user.id:
            raise UserNotRowCommentAuthorException()

        TrashHandler.trash(requesting_user, database.workspace, database, row_comment)

        mentions = list(row_comment.mentions(manager="objects_and_identities").all())
        row_comment_deleted.send(
            cls,
            row_comment=row_comment,
            user=requesting_user,
            mentions=mentions,
        )

    @classmethod
    def get_users_to_notify_for_comment(
        cls,
        row_comment: RowComment,
        user_ids_to_exclude=None,
    ) -> List[AbstractUser]:
        """
        Returns a list of users who should be notified about a new comment on a
        table row. This list will not include the sender of the comment.

        :param row_comment: The comment to notify users about.
        :param user_ids_to_exclude: A list of user ids to exclude from the
            returned list (i.e. users mentioned in the comment).
        :return: A list of users who should be notified about the comment.
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
            table = row_comment.table
            workspace = table.database.workspace
            users = [u.user for u in user_subscriptions]

            # Step 1: check table-level permission for all subscribed users.
            # This covers the common case where users have workspace or table
            # level access.
            table_allowed_users = CoreHandler().check_permission_for_multiple_actors(
                users,
                ReadRowCommentsOperationType.type,
                workspace=workspace,
                context=table,
            )
            table_allowed = {u.id for u in table_allowed_users}
            users_to_notify.extend(table_allowed_users)

            # Step 2: for users who didn't pass the table-level check, ask each view
            # ownership type if there are additional users that should be notified.
            # This allows ownership types like "restricted" to check view-level
            # permissions and row visibility within their views.
            remaining_users = [u for u in users if u.id not in table_allowed]
            if remaining_users:
                for ownership_type in view_ownership_type_registry.get_all():
                    additional = ownership_type.get_users_to_notify_for_row_comment(
                        table,
                        row_comment.row_id,
                        remaining_users,
                    )
                    users_to_notify.extend(additional)

        return users_to_notify

    @classmethod
    def update_row_comments_notification_mode(
        cls,
        user: AbstractUser,
        table_id: int,
        row_id: int,
        mode: RowCommentsNotificationModes,
        include_user_in_signal=False,
        view_id: Optional[int] = None,
        skip_permission_check: bool = False,
    ):
        """
        Updates the user's notification settings for comments on a specific
        table row. It either creates a database entry to notify the user about
        all comments on that row, or deletes the entry if the user prefers
        notifications only when mentioned. In this last case, the proper
        notification_type will take care to send the notification to the
        mentioned user.

        :param user: The user who is subscribing to the row's comments.
        :param table_id: The table to find the row in.
        :param row_id: The id of the row to subscribe to.
        :param mode: The subscription mode.
        :param include_user_in_signal: If True, the user sessions will be
            included in the signal that is sent.
        :param view_id: Optionally provide a view id for permission fallback.
        :param skip_permission_check: If True, skip the permission check.
            This is used when the method is called internally from a signal
            handler where the caller has already verified access.
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

        if not skip_permission_check:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, table.database.workspace
            )

            view = _get_view_if_provided(user, view_id)
            check_permissions_with_view_fallback(
                ReadRowCommentsOperationType.type,
                ReadViewRowCommentsOperationType.type,
                user,
                table,
                view,
                row_ids=[row_id],
            )

            RowHandler().has_row(user, table, row_id, raise_error=True, view=view)

        RowCommentsNotificationMode.objects.update_or_create(
            table=table, row_id=row_id, user=user, defaults={"mode": mode}
        )

        row_comments_notification_mode_updated.send(
            cls,
            user=user,
            table=table,
            row_id=int(row_id),
            mode=mode,
            include_user_in_signal=include_user_in_signal,
        )
