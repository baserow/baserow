import pytest
from pydantic_ai import Tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

from baserow_enterprise.assistant.action_memory import get_mutation_evidence
from baserow_enterprise.assistant.tools.database.tools import (
    create_row_comments,
    list_row_comments,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.tools import (
    MAX_COMMENTS_PER_CALL,
    RowCommentCreate,
)

from .utils import make_test_ctx


def _setup(data_fixture, **user_kwargs):
    user = data_fixture.create_user(**user_kwargs)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table, _, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Acme"]],
    )
    return make_test_ctx(user, workspace), table, rows[0]


@pytest.mark.django_db
def test_kuma_posts_and_reads_a_row_comment(premium_data_fixture, settings):
    settings.DEBUG = True
    ctx, table, row = _setup(premium_data_fixture, has_active_premium_license=True)

    created = create_row_comments(
        ctx,
        table.id,
        [RowCommentCreate(row_id=row.id, text="I called them")],
        thought="add the note",
    )

    assert created["errors"] == []
    listed = list_row_comments(ctx, table.id, row.id, thought="read the note")
    assert [comment["text"] for comment in listed["comments"]] == ["I called them"]


@pytest.mark.django_db
def test_kuma_row_comments_need_premium(data_fixture):
    ctx, table, row = _setup(data_fixture)

    with pytest.raises(FeaturesNotAvailableError):
        list_row_comments(ctx, table.id, row.id, thought="read")


def _evidence_of(result):
    return get_mutation_evidence(
        [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        "create_row_comments", {"thought": "x"}, tool_call_id="1"
                    )
                ]
            ),
            ModelRequest(
                parts=[ToolReturnPart("create_row_comments", result, tool_call_id="1")]
            ),
        ]
    )[0]


@pytest.mark.django_db
def test_kuma_counts_a_posted_comment_as_a_completed_change(
    premium_data_fixture, settings
):
    # Kuma only lets the model claim a change when the result shows one.
    settings.DEBUG = True
    ctx, table, row = _setup(premium_data_fixture, has_active_premium_license=True)

    posted = create_row_comments(
        ctx, table.id, [RowCommentCreate(row_id=row.id, text="x")], thought="x"
    )
    partly = create_row_comments(
        ctx,
        table.id,
        [
            RowCommentCreate(row_id=row.id, text="x"),
            RowCommentCreate(row_id=999999, text="y"),
        ],
        thought="x",
    )
    failed = create_row_comments(
        ctx, table.id, [RowCommentCreate(row_id=999999, text="y")], thought="x"
    )

    assert _evidence_of(posted).completed
    assert _evidence_of(partly).changed and not _evidence_of(partly).completed
    assert not _evidence_of(failed).changed


def test_kuma_create_row_comments_limits_a_batch():
    schema = Tool(create_row_comments, takes_ctx=True).function_schema.json_schema

    assert schema["properties"]["comments"]["maxItems"] == MAX_COMMENTS_PER_CALL
