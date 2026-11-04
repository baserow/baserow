"""Tests for the row comment tools shared by MCP and Kuma."""

import json
from unittest.mock import patch

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pydantic import ValidationError

from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.table.models import Table
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.actions import CreateRowCommentActionType
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import RowComment
from baserow_premium.row_comments.tools import (
    MAX_COMMENTS_PER_CALL,
    RowCommentCreate,
    create_row_comments,
    list_row_comments,
)


@pytest.fixture(autouse=True)
def debug_licences(settings):
    # `has_active_premium_license` only works in debug mode.
    settings.DEBUG = True


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _setup(fixture, **user_kwargs):
    user = fixture.create_user(first_name="Anna", **user_kwargs)
    workspace = fixture.create_workspace(user=user)
    database = fixture.create_database_application(workspace=workspace)
    table, _, rows = fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Acme"], ["Globex"]],
    )
    return ToolContext(user=user, workspace=workspace), table, rows


@pytest.mark.django_db
def test_create_and_list_row_comment_as_plain_text(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)

    result = create_row_comments(
        ctx,
        table.id,
        [RowCommentCreate(row_id=rows[0].id, text="Call back Monday")],
    )

    comment = RowComment.objects.get()
    assert result == {
        "created_comments": [
            {"id": comment.id, "row_id": rows[0].id, "text": "Call back Monday"}
        ],
        "errors": [],
    }
    listed = list_row_comments(ctx, table.id, rows[0].id)
    assert listed["count"] == 1
    assert listed["comments"] == [
        {
            "id": comment.id,
            "user_name": "Anna",
            "text": "Call back Monday",
            "created_on": comment.created_on.isoformat(),
            "edited": False,
        }
    ]


@pytest.mark.django_db
def test_create_row_comment_reports_the_action(premium_data_fixture):
    # The action type isn't undoable: it stores no action, it reaches the audit log
    # through this signal.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)

    with patch("baserow.core.action.registries.action_done.send") as send:
        create_row_comments(
            ctx, table.id, [RowCommentCreate(row_id=rows[0].id, text="x")]
        )

    assert send.call_args.kwargs["action_type"] is CreateRowCommentActionType


@pytest.mark.django_db
def test_create_row_comment_on_missing_row_keeps_the_others(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)

    result = create_row_comments(
        ctx,
        table.id,
        [
            RowCommentCreate(row_id=999999, text="x"),
            RowCommentCreate(row_id=rows[1].id, text="y"),
        ],
    )

    assert result["errors"] == [
        {"index": 0, "row_id": 999999, "error": "Not found in this workspace."}
    ]
    assert [c["row_id"] for c in result["created_comments"]] == [rows[1].id]
    assert RowComment.objects.count() == 1


@pytest.mark.django_db
def test_list_row_comments_on_row_missing_from_table(premium_data_fixture):
    ctx, table, _ = _setup(premium_data_fixture, has_active_premium_license=True)

    with pytest.raises(RowDoesNotExist):
        list_row_comments(ctx, table.id, 999999)


@pytest.mark.django_db
def test_list_row_comments_newest_first_and_paged(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    for text in ("first", "second", "third"):
        create_row_comments(
            ctx, table.id, [RowCommentCreate(row_id=rows[0].id, text=text)]
        )

    page_1 = list_row_comments(ctx, table.id, rows[0].id, size=2)
    page_2 = list_row_comments(ctx, table.id, rows[0].id, page=2, size=2)

    assert [c["text"] for c in page_1["comments"]] == ["third", "second"]
    assert [c["text"] for c in page_2["comments"]] == ["first"]
    assert page_1["count"] == page_2["count"] == 3


@pytest.mark.django_db
def test_list_row_comments_returns_every_paragraph_and_mention(premium_data_fixture):
    # A comment written in the UI can hold several paragraphs and mentions.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    message = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Line one"}]},
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Ask "},
                    {
                        "type": "mention",
                        "attrs": {"id": ctx.user.id, "label": "Anna"},
                    },
                ],
            },
        ],
    }
    RowCommentHandler.create_comment(ctx.user, table.id, rows[0].id, message)

    text = list_row_comments(ctx, table.id, rows[0].id)["comments"][0]["text"]

    assert text == "Line one\nAsk @Anna"


@pytest.mark.django_db
def test_list_row_comments_reads_a_mention_without_a_label(premium_data_fixture):
    # The API accepts it, and one such comment must not make the row unreadable.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Ask "},
                    {"type": "mention", "attrs": {"id": ctx.user.id}},
                ],
            }
        ],
    }
    RowCommentHandler.create_comment(ctx.user, table.id, rows[0].id, message)

    text = list_row_comments(ctx, table.id, rows[0].id)["comments"][0]["text"]

    assert text == "Ask @"


@pytest.mark.django_db
def test_list_row_comments_reads_a_label_that_is_no_string(premium_data_fixture):
    # The API accepts it, and one such comment must not make the row unreadable.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"id": ctx.user.id, "label": 123}}
                ],
            }
        ],
    }
    RowCommentHandler.create_comment(ctx.user, table.id, rows[0].id, message)

    text = list_row_comments(ctx, table.id, rows[0].id)["comments"][0]["text"]

    assert text == "@123"


@pytest.mark.django_db
def test_list_row_comments_reads_a_document_without_content(premium_data_fixture):
    # The API accepts it, and one such comment must not make the row unreadable.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    RowCommentHandler.create_comment(ctx.user, table.id, rows[0].id, {"type": "doc"})

    assert list_row_comments(ctx, table.id, rows[0].id)["comments"][0]["text"] == ""


@pytest.mark.django_db
def test_create_row_comment_keeps_lines(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)

    result = create_row_comments(
        ctx,
        table.id,
        [RowCommentCreate(row_id=rows[0].id, text="Line one\n\nLine two")],
    )

    assert result["errors"] == []
    text = list_row_comments(ctx, table.id, rows[0].id)["comments"][0]["text"]
    assert text == "Line one\nLine two"


def test_row_comment_text_must_hold_something():
    with pytest.raises(ValidationError):
        RowCommentCreate(row_id=1, text="   ")
    with pytest.raises(ValidationError):
        RowCommentCreate(row_id=1, text="x" * 10001)


@pytest.mark.django_db
def test_row_comments_need_premium(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture)

    with pytest.raises(FeaturesNotAvailableError):
        list_row_comments(ctx, table.id, rows[0].id)
    with pytest.raises(FeaturesNotAvailableError):
        create_row_comments(
            ctx, table.id, [RowCommentCreate(row_id=rows[0].id, text="x")]
        )

    assert RowComment.objects.count() == 0


@pytest.mark.django_db
def test_row_comments_hide_table_of_other_workspace(premium_data_fixture):
    ctx, _, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    _, other_table, other_rows = _setup(
        premium_data_fixture, has_active_premium_license=True
    )
    # A member of both workspaces, using an endpoint for the first.
    premium_data_fixture.create_user_workspace(
        user=ctx.user, workspace=other_table.database.workspace
    )

    with pytest.raises(Table.DoesNotExist):
        list_row_comments(ctx, other_table.id, other_rows[0].id)
    with pytest.raises(Table.DoesNotExist):
        create_row_comments(
            ctx, other_table.id, [RowCommentCreate(row_id=other_rows[0].id, text="x")]
        )

    assert RowComment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_create_row_comments_over_mcp(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user,
        workspace=ctx.workspace,
        allowed_tools=["create_row_comments", "list_row_comments"],
    )

    result = _call(
        endpoint,
        "create_row_comments",
        {"table_id": table.id, "comments": [{"row_id": rows[0].id, "text": "Hi"}]},
    )
    assert not result.isError
    assert json.loads(result.content[0].text)["created_comments"][0]["text"] == "Hi"

    result = _call(
        endpoint, "list_row_comments", {"table_id": table.id, "row_id": rows[0].id}
    )
    assert json.loads(result.content[0].text)["comments"][0]["text"] == "Hi"


@pytest.mark.django_db(transaction=True)
def test_create_row_comments_over_mcp_rejects_empty_list(premium_data_fixture):
    ctx, table, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user, workspace=ctx.workspace, allowed_tools=["create_row_comments"]
    )

    result = _call(
        endpoint, "create_row_comments", {"table_id": table.id, "comments": []}
    )

    assert result.isError
    assert RowComment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_create_row_comments_over_mcp_rejects_too_many(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user, workspace=ctx.workspace, allowed_tools=["create_row_comments"]
    )
    comment = {"row_id": rows[0].id, "text": "Hi"}

    result = _call(
        endpoint,
        "create_row_comments",
        {"table_id": table.id, "comments": [comment] * (MAX_COMMENTS_PER_CALL + 1)},
    )

    assert result.isError
    assert RowComment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_row_comments_over_mcp_tell_the_client_about_the_licence(premium_data_fixture):
    ctx, table, rows = _setup(premium_data_fixture)
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user, workspace=ctx.workspace, allowed_tools=["create_row_comments"]
    )

    result = _call(
        endpoint,
        "create_row_comments",
        {"table_id": table.id, "comments": [{"row_id": rows[0].id, "text": "Hi"}]},
    )

    assert result.isError
    assert result.content[0].text == (
        "The related user does not have access to these features."
    )
    assert RowComment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_row_comment_tools_work_outside_a_transaction(premium_data_fixture):
    # The MCP server and Kuma call the tools outside a transaction, unlike a test's
    # database fixture.
    ctx, table, rows = _setup(premium_data_fixture, has_active_premium_license=True)

    created = create_row_comments(
        ctx, table.id, [RowCommentCreate(row_id=rows[0].id, text="Hi")]
    )
    listed = list_row_comments(ctx, table.id, rows[0].id)

    assert created["errors"] == []
    assert listed["comments"][0]["text"] == "Hi"
