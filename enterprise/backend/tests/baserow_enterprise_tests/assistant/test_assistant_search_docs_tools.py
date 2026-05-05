import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from baserow_enterprise.assistant.tools.search_user_docs.tools import (
    _TOOL_QUERY_RE,
    SearchDocsResult,
    search_user_docs,
)

from .utils import make_test_ctx

# search_user_docs is async, so we need this to allow sync ORM calls from
# data_fixture inside async tests.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


class TestToolQueryGuard:
    """Tests for the tool-introspection regex guard."""

    @pytest.mark.parametrize(
        "query",
        [
            "list_tables",
            "create_fields",
            "get_tables_schema",
            "update_rows",
            "delete_rows",
            "generate_formula",
            "create_view_filters",
            "search_user_docs",
            "navigate tool parameters",
        ],
    )
    def test_rejects_tool_introspection_queries(self, query):
        assert _TOOL_QUERY_RE.search(query) is not None

    @pytest.mark.parametrize(
        "query",
        [
            "How to create a webhook in Baserow",
            "How to link tables in Baserow",
            "Baserow form view",
            "How do I import data into Baserow",
        ],
    )
    def test_allows_legitimate_queries(self, query):
        assert _TOOL_QUERY_RE.search(query) is None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_search_user_docs_rejects_tool_introspection(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    result = await search_user_docs(
        ctx, question="list_tables", thought="looking up tool"
    )

    assert result["reliability"] == 0.0
    assert "REJECTED" in result["reliability_note"]
    assert result["sources"] == []


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_search_user_docs_handles_empty_results(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    with patch(
        "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
    ) as mock_handler_cls:
        mock_handler_cls.return_value.search.return_value = []

        result = await search_user_docs(
            ctx, question="How to use webhooks in Baserow", thought="user asks"
        )

    assert result["reliability"] == 0.0
    assert "Nothing found" in result["answer"]


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_search_user_docs_does_not_add_sources_for_nothing_found_prediction(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)
    chunk = MagicMock(content="Some unrelated documentation.")
    chunk.source_document = MagicMock(source_url="https://example.com/docs")

    with (
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
        ) as mock_handler_cls,
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.search_docs_agent.run",
            new_callable=AsyncMock,
        ) as mock_run,
        patch(
            "baserow_enterprise.assistant.model_profiles.get_model_string",
            return_value="test/model",
        ),
        patch(
            "baserow_enterprise.assistant.retrying_model._resolve_model",
            return_value=MagicMock(),
        ),
    ):
        mock_handler_cls.return_value.search.return_value = [chunk]
        mock_run.return_value = MagicMock(
            output=SearchDocsResult(
                answer="Nothing found in the documentation.",
                reliability=1.0,
                sources=["https://example.com/docs"],
            )
        )

        result = await search_user_docs(
            ctx, question="Does Baserow support imaginary widgets?", thought="user asks"
        )

    assert result["reliability"] == 0.0
    assert result["sources"] == []
    assert ctx.deps.sources == []


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_search_user_docs_handles_error(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    with patch(
        "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
    ) as mock_handler_cls:
        mock_handler_cls.return_value.search.side_effect = RuntimeError("db error")

        result = await search_user_docs(
            ctx, question="How to use webhooks", thought="user asks"
        )

    assert result["reliability"] == 0.0
    assert "error" in result["answer"].lower()
