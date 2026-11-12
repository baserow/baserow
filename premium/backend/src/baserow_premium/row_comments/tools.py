"""
Row comment tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from pydantic import BaseModel, Field, StringConstraints

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import PermissionException
from baserow.core.prosemirror.utils import (
    prosemirror_doc_from_plain_text,
    prosemirror_doc_to_plain_text,
)
from baserow.core.tools import ToolContext, tool_execution
from baserow.core.tools.errors import item_error_message
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.actions import CreateRowCommentActionType
from baserow_premium.row_comments.handler import RowCommentHandler

MAX_PAGE_SIZE = 100
# A comment costs about nine queries and its own transaction, and can notify people.
MAX_COMMENTS_PER_CALL = 100


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
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of comments a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    List the comments of a row as plain text, newest first. Needs a premium licence.
    """

    table = _get_table(ctx, table_id)
    comments = RowCommentHandler.get_comments(ctx.user, table.id, row_id)
    start = (page - 1) * size

    return {
        "comments": [
            {
                "id": comment.id,
                "user_name": comment.user.first_name if comment.user else None,
                "text": _to_plain_text(comment.message),
                "created_on": comment.created_on.isoformat(),
                "edited": comment.updated_on > comment.created_on,
            }
            for comment in comments[start : start + size]
        ],
        "count": comments.count(),
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
    that fails is reported in errors and the others are still posted. Needs a premium
    licence.
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
