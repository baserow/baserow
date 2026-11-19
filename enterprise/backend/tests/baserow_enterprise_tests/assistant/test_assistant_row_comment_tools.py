import pytest
from baserow_premium_tests.row_comments.utils import create_comment_scenario
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
    search_row_comments,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.tools import (
    MAX_COMMENTS_PER_CALL,
    MAX_PAGE,
    MAX_SEARCHED_TABLES,
    MAX_USER_REFERENCES,
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
def test_kuma_posts_and_reads_a_row_comment(
    data_fixture, enable_enterprise, synced_roles
):
    ctx, table, row = _setup(data_fixture)

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
def test_kuma_finds_the_comments_that_mention_its_user(
    data_fixture, enable_enterprise, synced_roles
):
    scenario = create_comment_scenario(data_fixture)
    ctx = make_test_ctx(scenario.ctx.user, scenario.ctx.workspace)

    found = search_row_comments(
        ctx, scenario.database.id, thought="my mentions", mentioned_users=[0]
    )

    assert [(comment["table"], comment["row"]) for comment in found["comments"]] == [
        ("Tasks", "Mail"),
        ("Projects", "Globex"),
    ]
    assert found["has_more"] is False


@pytest.mark.django_db
def test_kuma_row_comment_calls_require_a_workspace_licence(
    premium_data_fixture, settings
):
    settings.DEBUG = True
    ctx, table, row = _setup(premium_data_fixture, has_active_premium_license=True)

    with pytest.raises(FeaturesNotAvailableError):
        list_row_comments(ctx, table.id, row.id, thought="read")
    with pytest.raises(FeaturesNotAvailableError):
        search_row_comments(ctx, table.database_id, thought="search")
    with pytest.raises(FeaturesNotAvailableError):
        create_row_comments(
            ctx,
            table.id,
            [RowCommentCreate(row_id=row.id, text="Hello")],
            thought="post",
        )


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
    data_fixture, enable_enterprise, synced_roles
):
    # Kuma only lets the model claim a change when the result shows one.
    ctx, table, row = _setup(data_fixture)

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


def test_kuma_search_row_comments_limits_its_lists():
    schema = Tool(search_row_comments, takes_ctx=True).function_schema.json_schema

    def max_items(name):
        return schema["properties"][name]["anyOf"][0]["maxItems"]

    assert max_items("table_ids") == MAX_SEARCHED_TABLES
    assert max_items("mentioned_users") == MAX_USER_REFERENCES
    assert max_items("authors") == MAX_USER_REFERENCES


@pytest.mark.parametrize("tool", [list_row_comments, search_row_comments])
def test_kuma_row_comment_tools_limit_the_page(tool):
    schema = Tool(tool, takes_ctx=True).function_schema.json_schema

    assert schema["properties"]["page"]["maximum"] == MAX_PAGE
