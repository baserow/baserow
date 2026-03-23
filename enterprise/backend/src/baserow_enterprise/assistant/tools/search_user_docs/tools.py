import re
from typing import Annotated, Any

from django.utils.translation import gettext as _

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.models import KnowledgeBaseChunk

from .handler import KnowledgeBaseHandler

# Regex that matches assistant tool names in a search query.  Used to
# short-circuit search_user_docs when the model is trying to look up how
# its own tools work instead of answering a user question.
_TOOL_QUERY_RE = re.compile(
    r"(?:list|create|get|update|delete|generate|load|add)_"
    r"(?:tables?|fields?|views?|rows?|pages?|elements?|actions?|data_sources?|"
    r"theme|workflows?|view_filters?|formula|row_tools|"
    r"action_field_mapping|rows_in_table)"
    r"|search_user_docs"
    r"|\bnavigate\s+(?:tool|function|param)",
    re.IGNORECASE,
)


SEARCH_DOCS_INSTRUCTIONS = """\
Given a user question and documentation chunks as context, provide an accurate
and concise answer along with a reliability score.

CRITICAL: The context may contain documents retrieved by keyword similarity that
are NOT actually relevant to the user's question. You MUST carefully evaluate
each document's ACTUAL TOPIC before using it:

1. First, identify the SPECIFIC FEATURE or concept the user is asking about
2. For each document, check if it DIRECTLY explains that specific feature
3. IGNORE documents that merely mention similar keywords but cover different topics
   (e.g., if asked about "webhooks in Baserow", ignore docs about external
   webhook services or third-party integrations - only use docs about
   Baserow's native webhook feature)
4. Only use documents that would genuinely help answer THIS specific question

If no documents in the context actually address the user's question (even if
they contain similar words), respond with "Nothing found in the documentation."

Include instructions and URLs from the documentation when relevant.
Never fabricate answers or URLs.
"""


class SearchDocsResult(PydanticBaseModel):
    answer: str = Field(description="The answer to the user's question.")
    sources: list[str] = Field(
        default_factory=list,
        description=(
            "URLs of documents that were ACTUALLY USED to form the answer. "
            "Only include sources that directly addressed the question topic. "
            "Leave empty if no documents were relevant. Maximum 3 URLs, ordered by relevance."
        ),
    )
    reliability: float = Field(
        description=(
            "How well the RELEVANT documents (not all documents) support the answer. "
            "1.0 = found documents that directly and completely answer the question. "
            "0.5 = found partially relevant information. "
            "0.0 = no documents actually addressed the question (regardless of keyword matches)."
        )
    )


search_docs_agent: Agent[None, SearchDocsResult] = Agent(
    output_type=SearchDocsResult,
    instructions=SEARCH_DOCS_INSTRUCTIONS,
    name="search_docs_agent",
)


def format_context(chunks: list[KnowledgeBaseChunk]) -> dict[str, str]:
    """
    Formats the context as a mapping of source URLs to their combined content.

    :param chunks: The list of knowledge base chunks.
    :return: A dictionary mapping source URLs to their combined content.
    """

    context = {}
    for chunk in chunks:
        url = chunk.source_document.source_url
        content = chunk.content
        if url not in context:
            context[url] = content
        else:
            context[url] += "\n" + content

    return context


async def search_user_docs(
    ctx: RunContext[AssistantDeps],
    question: Annotated[
        str,
        (
            "A precise search query in English using Baserow terminology. "
            "Focus on the SPECIFIC Baserow feature being asked about. "
            "Include the feature name and action, e.g., 'How to create webhooks in Baserow' "
            "or 'Baserow table linking feature'. Avoid generic terms that could match "
            "unrelated documentation about third-party services or integrations."
        ),
    ],
    thought: Annotated[str, "Brief reasoning for calling this tool."],
) -> dict[str, Any]:
    """\
    Search Baserow end-user docs for feature guides. NOT for tool introspection. It doesn't provide any information about your own tools.

    WHEN to use: User explicitly asks how to do something in Baserow's UI, or wants to learn about a specific Baserow feature (e.g., linking tables, webhooks, forms).
    WHAT it does: Searches official Baserow end-user documentation and returns an answer with reliability score and source URLs.
    RETURNS: Answer, reliability score (0.0-1.0), reliability_note (HIGH/PARTIAL/LOW), source URLs. Always check reliability_note before using the answer.
    DO NOT USE when: Looking up how YOUR OWN tools work — you already know your tools from their names, descriptions, and schemas. Also not for API/programming documentation.

    IMPORTANT: Frame the question to target Baserow's NATIVE features specifically.
    For example, ask about "Baserow webhooks" not just "webhooks" to avoid getting
    results about external webhook services that integrate WITH Baserow.
    """

    tool_helpers = ctx.deps.tool_helpers

    # Guard: reject queries about the model's own tools.
    if _TOOL_QUERY_RE.search(question):
        logger.info("search_user_docs: rejected tool-introspection query: {}", question)
        return {
            "answer": (
                "STOP. This tool searches END-USER documentation only — "
                "it has no information about your tools. "
                "You already know how to use your tools from their names, "
                "descriptions, and parameter schemas. "
                "If a tool call failed, read the error message carefully "
                "and adjust the parameters."
            ),
            "reliability": 0.0,
            "reliability_note": "REJECTED: Tool-introspection query.",
            "sources": [],
        }

    tool_helpers.update_status(_("Exploring the knowledge base..."))

    try:
        return await _search_user_docs_impl(ctx, question)
    except Exception:
        logger.exception("search_user_docs failed for question: {}", question)
        return {
            "answer": "An error occurred while searching the documentation.",
            "reliability": 0.0,
            "reliability_note": (
                "LOW CONFIDENCE: The documentation search encountered an error. "
                "Inform the user that documentation search is temporarily "
                "unavailable and suggest they check baserow.io/docs directly."
            ),
            "sources": [],
        }


async def _search_user_docs_impl(
    ctx: RunContext[AssistantDeps],
    question: str,
) -> dict[str, Any]:
    """Inner implementation of search_user_docs, separated for error handling."""

    @sync_to_async
    def _search(question: str) -> list[KnowledgeBaseChunk]:
        chunks = KnowledgeBaseHandler().search(question, 15)
        return list(chunks)

    relevant_chunks = await _search(question)

    if not relevant_chunks:
        return {
            "answer": "Nothing found in the documentation.",
            "reliability": 0.0,
            "reliability_note": (
                "LOW CONFIDENCE: The documentation does not contain information about "
                "this topic. DO NOT provide an answer based on general knowledge or "
                "assumptions - the feature may not exist in Baserow. Tell the user: "
                "'I couldn't find information about this in the official Baserow "
                "documentation.' and suggest they check the community forum or "
                "contact support."
            ),
            "sources": [],
        }

    context = format_context(relevant_chunks)

    prompt = (
        f"Question: {question}\n\n"
        f"Documentation context (source URL -> content):\n{context}"
    )
    from baserow_enterprise.assistant.model_profiles import get_model_string
    from baserow_enterprise.assistant.retrying_model import _resolve_model

    agent_result = await search_docs_agent.run(
        prompt, model=_resolve_model(get_model_string())
    )
    prediction = agent_result.output

    sources = []
    available_urls = {chunk.source_document.source_url for chunk in relevant_chunks}
    for url in prediction.sources:
        # somehow LLMs sometimes return sources as objects
        if isinstance(url, dict) and "url" in url:
            url = url["url"]

        if not isinstance(url, str):
            continue

        if url in available_urls and url not in sources:
            sources.append(url)
            if len(sources) >= 3:
                break

    # Only fallback to available URLs if reliability is high AND we have a
    # real answer. Don't populate sources if the model indicated no relevant
    # docs were found.
    nothing_found = "nothing found" in prediction.answer.lower()
    if not sources and prediction.reliability > 0.8 and not nothing_found:
        sources = list(available_urls)[:3]

    # Override reliability to 0 if the model explicitly said nothing was
    # found. The model sometimes returns high reliability for "nothing
    # found" answers, which is semantically incorrect - we want reliability
    # to reflect whether we actually found useful information.
    reliability = 0.0 if nothing_found else prediction.reliability

    if reliability >= 0.7:
        reliability_note = (
            "HIGH CONFIDENCE: Answer is well-supported by the documentation."
        )
    elif reliability >= 0.4:
        reliability_note = (
            "PARTIAL MATCH: Some relevant information was found, but the "
            "documentation may not fully cover this topic. Supplement with "
            "general knowledge but warn the user that details may be incomplete."
        )
    else:
        reliability_note = (
            "LOW CONFIDENCE: The documentation does not contain information about "
            "this topic. DO NOT provide an answer based on general knowledge or "
            "assumptions - the feature may not exist in Baserow. Tell the user: "
            "'I couldn't find information about this in the official Baserow "
            "documentation.' and suggest they check the community forum or "
            "contact support."
        )

    if sources:
        ctx.deps.extend_sources(sources)

    return {
        "answer": prediction.answer,
        "reliability": reliability,
        "reliability_note": reliability_note,
        "sources": sources,
    }


TOOL_FUNCTIONS = [search_user_docs]
search_docs_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
