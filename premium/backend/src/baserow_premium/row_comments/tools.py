"""
Row comment tools shared by the clients that act for a user.
"""

from collections import defaultdict
from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch

from pydantic import BaseModel, Field, StringConstraints

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools.tables import get_database, permitted_tables
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.models import User
from baserow.core.prosemirror.utils import (
    prosemirror_doc_from_plain_text,
    prosemirror_doc_to_plain_text,
)
from baserow.core.tools import ToolContext, tool_execution
from baserow.core.tools.errors import ToolInputError, item_error_message
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.row_comments.actions import CreateRowCommentActionType
from baserow_premium.row_comments.handler import (
    ROW_COMMENT_SEARCH_OPERATIONS,
    RowCommentHandler,
)
from baserow_premium.row_comments.models import RowComment

MAX_PAGE_SIZE = 100
# A search reads the comments up to its page in every table.
MAX_PAGE = 100
# A comment costs about nine queries and its own transaction, and can notify people.
MAX_COMMENTS_PER_CALL = 100
# A search reads every table on its own, so a call stays bounded.
MAX_SEARCHED_TABLES = 50
MAX_USER_REFERENCES = 20
ACTING_USER = 0

UserReference = (
    int
    | Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
    ]
)
CommentPage = Annotated[
    int, Field(ge=1, le=MAX_PAGE, description="The page to return.")
]
SearchedTableIds = Annotated[
    list[int] | None,
    Field(
        max_length=MAX_SEARCHED_TABLES,
        description="Only search these tables of the database. Omit or leave empty "
        "to search every table whose rows and comments you can read.",
    ),
]
MentionedUsers = Annotated[
    list[UserReference] | None,
    Field(
        max_length=MAX_USER_REFERENCES,
        description="Only the comments that mention one of these users. Each is a "
        "user ID, 0 for the user these tools act as, or part of a name, which "
        "matches everyone whose name contains it.",
    ),
]
CommentAuthors = Annotated[
    list[UserReference] | None,
    Field(
        max_length=MAX_USER_REFERENCES,
        description="Only the comments written by one of these users, given like "
        "mentioned_users.",
    ),
]
CreatedAfter = Annotated[
    datetime | None,
    Field(description="Only the comments created at or after this moment."),
]
CreatedBefore = Annotated[
    datetime | None,
    Field(description="Only the comments created before this moment."),
]


class RowCommentCreate(BaseModel):
    row_id: int = Field(..., description="The ID of the row to comment on.")
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
    ] = Field(..., description="The comment, as plain text.")


def _get_table(ctx: ToolContext, table_id: int) -> Table:
    """
    A table of the context's workspace the user can see.

    :raises Table.DoesNotExist: When it is missing or outside the workspace.
    """

    return (
        TableHandler().list_workspace_tables(ctx.user, ctx.workspace).get(id=table_id)
    )


def _to_plain_text(message: dict[str, Any]) -> str:
    # prosemirror_doc_to_plain_text only reads a document's first block.
    return "\n".join(
        prosemirror_doc_to_plain_text({"type": "doc", "content": [block]})
        for block in message.get("content", [])
    )


def _from_plain_text(text: str) -> dict[str, Any]:
    # A document has one paragraph a line, and a paragraph's text can't be empty.
    return {
        "type": "doc",
        "content": [
            prosemirror_doc_from_plain_text(line)["content"][0]
            for line in text.splitlines()
            if line.strip()
        ],
    }


@tool_execution
def list_row_comments(
    ctx: ToolContext,
    table_id: Annotated[int, Field(description="The ID of the row's table.")],
    row_id: Annotated[int, Field(description="The ID of the row.")],
    page: CommentPage = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of comments a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    List the comments of a row as plain text, newest first.
    """

    table = _get_table(ctx, table_id)
    comments = RowCommentHandler.get_comments(ctx.user, table.id, row_id)
    start = (page - 1) * size
    listed = comments.prefetch_related(
        Prefetch("mentions", queryset=User.objects_and_identities.all())
    )[start : start + size]

    return {
        "comments": [_comment_values(comment) for comment in listed],
        "count": comments.count(),
    }


def parse_user_reference(reference: int | str) -> int | str:
    """
    :param reference: A user as a search names them.
    :return: The user's ID, which can be ``ACTING_USER``, or the part of a name.
    """

    text = str(reference).strip()
    return int(text) if text.isdecimal() else text


def _user_ids(ctx: ToolContext, users: list[int | str] | None) -> list[int] | None:
    """
    The IDs of the users a search names, or None when it names none.

    :param users: Each a user ID, ``ACTING_USER`` or part of a name.
    :raises ToolInputError: When a name matches nobody in the workspace.
    """

    if not users:
        return None
    collaborators = CoreHandler().get_workspace_collaborators(
        ctx.workspace, include_identities=True
    )
    user_ids = set()
    for user in users:
        reference = parse_user_reference(user)
        if isinstance(reference, int):
            user_ids.add(ctx.user.id if reference == ACTING_USER else reference)
            continue
        named = list(
            collaborators.filter(first_name__icontains=reference).values_list(
                "id", flat=True
            )
        )
        if not named:
            raise ToolInputError(f"Nobody in the workspace is named '{reference}'.")
        user_ids.update(named)
    return list(user_ids)


def _in_timezone(ctx: ToolContext, moment: datetime | None) -> datetime | None:
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=ZoneInfo(ctx.timezone or "UTC"))


def _searched_tables(
    ctx: ToolContext, database_id: int, table_ids: list[int] | None
) -> list[Table]:
    """
    The tables of a database a search reads: the given ones, or every table whose
    comments the user may read.

    :raises ApplicationDoesNotExist: When the user can't see the database.
    :raises Table.DoesNotExist: When a given table isn't one the user can see in
        the database.
    :raises ToolInputError: When there are more tables than one search reads.
    """

    tables = (
        TableHandler()
        .list_workspace_tables(ctx.user, ctx.workspace)
        .filter(database=get_database(ctx, database_id))
    )
    if not table_ids:
        searched = list(tables)
        for operation in ROW_COMMENT_SEARCH_OPERATIONS:
            searched = permitted_tables(ctx, searched, operation)
    else:
        found = tables.in_bulk(table_ids)
        missing = [table_id for table_id in table_ids if table_id not in found]
        if missing:
            raise Table.DoesNotExist(f"The database has no table with ID {missing[0]}.")
        searched = [found[table_id] for table_id in dict.fromkeys(table_ids)]
    if len(searched) > MAX_SEARCHED_TABLES:
        raise ToolInputError(
            f"The search reads {len(searched)} tables, and one search reads at most "
            f"{MAX_SEARCHED_TABLES}.",
            hint="Give table_ids to search some of the tables.",
        )
    return searched


def _row_names(
    ctx: ToolContext, tables: dict[int, Table], comments: list[RowComment]
) -> dict[tuple[int, int], str]:
    """
    :param tables: The searched tables, by ID.
    :param comments: The comments found.
    :return: The primary value of each commented row, by table and row ID. The
        rows of a table whose rows the user may not list are left out.
    """

    row_ids = defaultdict(set)
    for comment in comments:
        row_ids[comment.table_id].add(comment.row_id)
    listable = permitted_tables(
        ctx,
        [tables[table_id] for table_id in row_ids],
        ListRowsDatabaseTableOperationType.type,
    )
    return {
        (table.id, row_id): name
        for table in listable
        for row_id, name in RowHandler()
        .get_row_names(table, list(row_ids[table.id]))
        .items()
    }


def _comment_values(comment: RowComment, **place: Any) -> dict[str, Any]:
    """
    :param comment: A comment, with its author and mentions loaded.
    :param place: Where the comment is, for a result that covers several rows.
    :return: The comment as a tool returns it.
    """

    return {
        "id": comment.id,
        **place,
        "user_id": comment.user_id,
        "user_name": comment.user.first_name if comment.user else None,
        "text": _to_plain_text(comment.message),
        "mentions": [
            {"id": user.id, "name": user.first_name}
            for user in sorted(comment.mentions.all(), key=lambda user: user.id)
        ],
        "created_on": comment.created_on.isoformat(),
        "edited": comment.updated_on > comment.created_on,
    }


@tool_execution
def search_row_comments(
    ctx: ToolContext,
    database_id: Annotated[int, Field(description="The ID of the database to search.")],
    table_ids: SearchedTableIds = None,
    mentioned_users: MentionedUsers = None,
    authors: CommentAuthors = None,
    created_after: CreatedAfter = None,
    created_before: CreatedBefore = None,
    page: CommentPage = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of comments a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    Find the comments on the rows of a database, newest first, each with its table
    and row. Narrow them down by table, by who they mention, by who wrote them and
    by when they were written. has_more means there are more candidates. Pages can
    be short or empty if comments or their rows were removed. Go past the last page
    with created_before.
    """

    LicenseHandler.raise_if_user_doesnt_have_feature(PREMIUM, ctx.user, ctx.workspace)
    tables = {
        table.id: table for table in _searched_tables(ctx, database_id, table_ids)
    }
    found = RowCommentHandler.search_comments(
        ctx.user,
        ctx.workspace,
        list(tables.values()),
        mentioned_user_ids=_user_ids(ctx, mentioned_users),
        author_ids=_user_ids(ctx, authors),
        created_after=_in_timezone(ctx, created_after),
        created_before=_in_timezone(ctx, created_before),
        limit=size,
        offset=(page - 1) * size,
    )
    names = _row_names(ctx, tables, found.comments)

    return {
        "comments": [
            _comment_values(
                comment,
                table_id=comment.table_id,
                table=tables[comment.table_id].name,
                row_id=comment.row_id,
                row=names.get((comment.table_id, comment.row_id)),
            )
            for comment in found.comments
        ],
        "has_more": found.has_more,
    }


@tool_execution
def create_row_comments(
    ctx: ToolContext,
    table_id: Annotated[int, Field(description="The ID of the rows' table.")],
    comments: Annotated[
        list[RowCommentCreate],
        Field(
            max_length=MAX_COMMENTS_PER_CALL,
            description="The comments to post, each on one row.",
        ),
    ],
) -> dict[str, Any]:
    """
    Post plain text comments on rows of a table. Mentions aren't supported. A comment
    that fails is reported in errors and the others are still posted.
    """

    if not comments:
        raise DjangoValidationError("comments must hold at least one comment.")

    table = _get_table(ctx, table_id)
    created = []
    errors = []
    for index, comment in enumerate(comments):
        try:
            with transaction.atomic():
                row_comment = CreateRowCommentActionType.do(
                    ctx.user, table.id, comment.row_id, _from_plain_text(comment.text)
                )
        # Apply to the whole call, so every item would report the same.
        except (FeaturesNotAvailableError, PermissionException):
            raise
        except Exception as exc:
            errors.append(
                {
                    "index": index,
                    "row_id": comment.row_id,
                    "error": item_error_message(exc),
                }
            )
        else:
            created.append(
                {"id": row_comment.id, "row_id": comment.row_id, "text": comment.text}
            )

    return {"created_comments": created, "errors": errors}
