from typing import TYPE_CHECKING, Annotated, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

import udspy
from asgiref.sync import sync_to_async

from baserow.core.models import Workspace
from baserow_enterprise.assistant.models import KnowledgeBaseChunk
from baserow_enterprise.assistant.tools.registries import AssistantToolType

from .handler import KnowledgeBaseHandler

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


class SearchDocsSignature(udspy.Signature):
    """
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

    question: str = udspy.InputField()
    context: dict[str, str] = udspy.InputField(
        desc=(
            "A mapping of source URLs to documents. WARNING: These documents were "
            "retrieved by keyword similarity and may include irrelevant results. "
            "Carefully filter to only use documents that DIRECTLY address the question."
        )
    )

    answer: str = udspy.OutputField()
    sources: list[str] = udspy.OutputField(
        desc=(
            "URLs of documents that were ACTUALLY USED to form the answer. "
            "Only include sources that directly addressed the question topic. "
            "Leave empty if no documents were relevant. Maximum 3 URLs, ordered by relevance."
        )
    )
    reliability: float = udspy.OutputField(
        desc=(
            "How well the RELEVANT documents (not all documents) support the answer. "
            "1.0 = found documents that directly and completely answer the question. "
            "0.5 = found partially relevant information. "
            "0.0 = no documents actually addressed the question (regardless of keyword matches)."
        )
    )

    @classmethod
    def format_context(cls, chunks: list[KnowledgeBaseChunk]) -> dict[str, str]:
        """
        Formats the context as a list of strings for the signature.
        Each string is formatted as "Source URL: content".

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


def get_search_user_docs_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[str], dict[str, Any]]:
    """
    Returns a tool function that searches Baserow's knowledge base and uses an LLM
    to filter and synthesize relevant documentation into a focused answer.

    The search retrieves documents by keyword similarity, then the LLM evaluates
    each document's actual relevance to the question before generating an answer.
    """

    async def search_user_docs(
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
    ) -> dict[str, Any]:
        """
        Search Baserow's official documentation for user guides and feature
        explanations.

        PURPOSE: Provides end-user documentation about Baserow's built-in
        features and how to use them through the UI.

        USE WHEN: The user asks how to do something in Baserow, wants to learn
        about a Baserow feature, or needs step-by-step instructions.

        DO NOT USE FOR: Agent tool usage, API implementation details, or
        programming help.

        IMPORTANT: Frame the question to target Baserow's NATIVE features
        specifically. For example, ask about "Baserow webhooks" not just
        "webhooks" to avoid getting results about external webhook services that
        integrate WITH Baserow.
        """

        nonlocal tool_helpers

        tool_helpers.update_status(_("Exploring the knowledge base..."))

        @sync_to_async
        def _search(question: str) -> list[KnowledgeBaseChunk]:
            chunks = KnowledgeBaseHandler().search(question, 15)
            return list(chunks)

        searcher = udspy.ChainOfThought(SearchDocsSignature)
        relevant_chunks = await _search(question)
        prediction = await searcher.aexecute(
            question=question,
            context=SearchDocsSignature.format_context(relevant_chunks),
            stream=True,
        )

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

        return {
            "answer": prediction.answer,
            "reliability": reliability,
            "reliability_note": reliability_note,
            "sources": sources,
        }

    return search_user_docs


class SearchDocsToolType(AssistantToolType):
    type = "search_user_docs"

    def can_use(
        self, user: AbstractUser, workspace: Workspace, *args, **kwargs
    ) -> bool:
        return KnowledgeBaseHandler().can_search()

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_search_user_docs_tool(user, workspace, tool_helpers)
