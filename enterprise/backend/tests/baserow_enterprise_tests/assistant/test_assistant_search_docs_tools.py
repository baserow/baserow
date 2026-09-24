import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

from baserow_enterprise.assistant.model_profiles import SUBAGENT
from baserow_enterprise.assistant.tools.search_user_docs.tools import (
    _TOOL_QUERY_RE,
    SearchDocsResult,
    search_user_docs,
)

from .utils import make_test_ctx

# search_user_docs is async, so we need this to allow sync ORM calls from
# data_fixture inside async tests.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_name, native, first_error",
    [
        ("openai/gpt-oss-120b", True, None),
        ("openai/gpt-oss-20b", True, None),
        ("llama-3.3-70b-versatile", False, None),
        ("openai/gpt-oss-120b", True, "reliability"),
        ("openai/gpt-oss-120b", True, "source"),
    ],
)
async def test_docs_synthesis_uses_supported_output_protocol(
    data_fixture, model_name, native, first_error
):
    """Exercise the real agent and Groq wire format, including typed validation."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    source = "https://example.com/tokens"
    answer = "Create a database token in Settings."
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        result = {"answer": answer, "sources": [source], "reliability": 0.9}
        if len(requests) == 1:
            if first_error == "reliability":
                result["reliability"] = 1.5
            elif first_error == "source":
                result["sources"] = ["https://example.com/invented"]
        if native:
            response_format = payload["response_format"]
            assert response_format["type"] == "json_schema"
            definition = response_format["json_schema"]
            assert definition["strict"] is True
            schema = definition["schema"]
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == {"answer", "sources", "reliability"}
            assert not payload.get("tools")
            message = {"role": "assistant", "content": json.dumps(result)}
            reason = "stop"
        else:
            assert "response_format" not in payload
            name = payload["tools"][0]["function"]["name"]
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "result-1",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(result)},
                    }
                ],
            }
            reason = "tool_calls"
        return httpx.Response(
            200,
            json={
                "id": "docs-synthesis",
                "object": "chat.completion",
                "created": 0,
                "model": model_name,
                "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        profile = MagicMock(model_string=f"groq:{model_name}")
        profile.get_settings.return_value = {}
        profile.create_model.return_value = GroqModel(
            model_name, provider=GroqProvider(api_key="test-only", http_client=client)
        )
        ctx = make_test_ctx(user, workspace, model_profile=profile)
        chunk = MagicMock(content=answer)
        chunk.source_document = MagicMock(title="Tokens", source_url=source)
        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.tools.KnowledgeBaseHandler"
        ) as handler:
            handler.return_value.search.return_value = [chunk]
            result = await search_user_docs(
                ctx, question="How do I create a database token?", thought="user asks"
            )

    assert result["answer"] == answer
    assert result["sources"] == ctx.deps.sources == [source]
    assert result["reliability"] == 0.9
    assert len(requests) == (2 if first_error else 1)
    if first_error == "reliability":
        assert "less than or equal to 1" in json.dumps(requests[1]["messages"])


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
    assert model_profile.create_model.call_count == mock_run.call_count == 2


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
    assert run.call_count == 2


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
    profile.get_settings.return_value = {"temperature": 0.3, "timeout": 20}
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
    profile.get_settings.assert_called_once_with(SUBAGENT)
    assert run.call_args.kwargs["model_settings"] == {
        "temperature": 0.3,
        "timeout": 20,
    }


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_search_user_docs_recovers_supported_partial_facts_once(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    profile = MagicMock()
    profile.get_settings.return_value = {"temperature": 0.3}
    ctx = make_test_ctx(user, workspace, model_profile=profile)
    chunk = MagicMock(content="Cards can display a selected file field as their cover.")
    chunk.source_document = MagicMock(
        title="Cards guide", source_url="https://example.com/cards"
    )
    partial = SearchDocsResult(
        answer="Cards display a file field as their cover; cropping is unverified.",
        sources=["https://example.com/cards"],
        reliability=0.5,
    )
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
        model = MagicMock()
        model.__aenter__.return_value = model
        profile.create_model.return_value = model
        run.side_effect = [
            MagicMock(
                output=SearchDocsResult(
                    answer="Nothing found in the documentation.", reliability=0
                )
            ),
            MagicMock(output=partial),
        ]
        result = await search_user_docs(
            ctx, question="Can I crop a card cover?", thought="user asks"
        )
    assert result["answer"] == partial.answer
    assert result["sources"] == partial.sources == ctx.deps.sources
    assert result["reliability"] == 0.5
    assert run.call_count == profile.create_model.call_count == 2
    assert "underlying task" in run.call_args_list[1].args[0]
    assert run.call_args_list[1].args[0].endswith(run.call_args_list[0].args[0])
    handler.return_value.search.assert_called_once_with("Can I crop a card cover?", 30)


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
