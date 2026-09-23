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
@pytest.mark.parametrize(
    "answer",
    [
        "Nothing found in the documentation.",
        "Nothing found in the documentation",
        "  NOTHING \n found in the documentation?!  ",
    ],
)
async def test_search_user_docs_does_not_add_sources_for_nothing_found_prediction(
    data_fixture,
    answer,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    model_profile = MagicMock()
    ctx = make_test_ctx(user, workspace, model_profile=model_profile)
    chunk = MagicMock(content="Some unrelated documentation.")
    chunk.source_document = MagicMock(
        title="Unrelated documentation", source_url="https://example.com/docs"
    )

    with (
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
        ) as mock_handler_cls,
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.search_docs_agent.run",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        mock_handler_cls.return_value.search.return_value = [chunk]
        mock_run.return_value = MagicMock(
            output=SearchDocsResult(
                answer=answer,
                reliability=1.0,
                sources=["https://example.com/docs"],
            )
        )
        model = MagicMock()
        model.__aenter__.return_value = model
        model_profile.create_model.return_value = model

        result = await search_user_docs(
            ctx, question="Does Baserow support imaginary widgets?", thought="user asks"
        )

    assert result["reliability"] == 0.0
    assert result["sources"] == []
    assert ctx.deps.sources == []
    model_profile.create_model.assert_called_once_with()


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


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.parametrize("sources", [[], ["https://example.com/invented"]])
async def test_search_user_docs_does_not_invent_source_attribution(
    data_fixture, sources
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    profile = MagicMock()
    ctx = make_test_ctx(user, workspace, model_profile=profile)
    chunk = MagicMock(content="The rows guide describes editing rows.")
    chunk.source_document = MagicMock(
        title="Rows", source_url="https://example.com/rows"
    )
    model = MagicMock()
    model.__aenter__.return_value = model
    profile.create_model.return_value = model
    with (
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
        ) as handler,
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.search_docs_agent.run",
            new_callable=AsyncMock,
        ) as run,
    ):
        handler.return_value.search.return_value = [chunk]
        run.return_value = MagicMock(
            output=SearchDocsResult(
                answer="An unsupported feature exists.",
                sources=sources,
                reliability=1.0,
            )
        )
        result = await search_user_docs(
            ctx, question="How do I edit rows?", thought="user asks"
        )
    assert result["reliability"] == 0.0
    assert result["sources"] == []
    assert ctx.deps.sources == []
    assert "unsupported feature exists" not in result["answer"]


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [
        "You can choose the cover field. These passages do not establish custom cropping controls.",
        "Nothing found about custom cropping. The documented cover field can be selected.",
        "Nothing found in the documentation about cropping. You can choose the cover field.",
    ],
)
async def test_search_user_docs_preserves_cited_partial_answer(data_fixture, answer):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    profile = MagicMock()
    ctx = make_test_ctx(user, workspace, model_profile=profile)
    chunk = MagicMock(content="Cards can display a selected file field as their cover.")
    chunk.source_document = MagicMock(
        title="Cards guide", source_url="https://example.com/cards"
    )
    model = MagicMock()
    model.__aenter__.return_value = model
    profile.create_model.return_value = model
    with (
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
        ) as handler,
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.search_docs_agent.run",
            new_callable=AsyncMock,
        ) as run,
    ):
        handler.return_value.search.return_value = [chunk]
        run.return_value = MagicMock(
            output=SearchDocsResult(
                answer=answer,
                sources=["https://example.com/cards"],
                reliability=0.5,
            )
        )
        result = await search_user_docs(
            ctx, question="How do I configure card covers?", thought="user asks"
        )
    assert result["answer"] == answer
    assert result["reliability"] == 0.5
    assert result["sources"] == ["https://example.com/cards"]
    assert ctx.deps.sources == ["https://example.com/cards"]
    assert "PARTIAL MATCH" in result["reliability_note"]
    assert "Supplement with general knowledge" not in result["reliability_note"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_hybrid_context_retains_midrank_semantic_evidence(data_fixture):
    import json

    from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS
    from baserow_enterprise.assistant.models import (
        KnowledgeBaseChunk,
        KnowledgeBaseDocument,
    )

    KnowledgeBaseChunk.try_init_vector_field()
    for index in range(40):
        lexical = index >= 20
        doc = KnowledgeBaseDocument.objects.create(
            title="Reference phrase" if lexical else f"Topic {index}",
            slug=f"topic-{index}",
            source_url=f"https://example.com/topic-{index}",
            status=KnowledgeBaseDocument.Status.READY,
        )
        KnowledgeBaseChunk.objects.create(
            source_document=doc,
            index=0,
            content="The documented answer." if index == 11 else "Other evidence.",
            embedding=[-1.0 if lexical else 1.0 - index * 0.01]
            + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
        )
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    profile = MagicMock()
    ctx = make_test_ctx(user, workspace, model_profile=profile)
    model = MagicMock()
    model.__aenter__.return_value = model
    profile.create_model.return_value = model
    with (
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.VectorHandler.embed_texts",
            return_value=[[1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1)],
        ),
        patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.search_docs_agent.run",
            new_callable=AsyncMock,
        ) as run,
    ):
        run.return_value = MagicMock(
            output=SearchDocsResult(
                answer="The documented answer.",
                sources=["https://example.com/topic-11"],
                reliability=1.0,
            )
        )
        result = await search_user_docs(
            ctx, question="How do I use reference phrase?", thought="user asks"
        )
    passages = json.loads(
        run.call_args.args[0].split("Documentation passages:\n", 1)[1]
    )
    assert any(passage["content"] == "The documented answer." for passage in passages)
    assert len(passages) <= 30
    assert sum(len(passage["content"]) for passage in passages) <= 30_000
    assert result["sources"] == ["https://example.com/topic-11"]
    assert result["reliability"] == 1.0
