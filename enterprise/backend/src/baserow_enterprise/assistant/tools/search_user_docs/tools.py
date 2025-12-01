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
    Given a user question and the relevant documentation chunks as context, provide a an
    accurate and concise answer along with a reliability score. If the documentation
    provides instructions or URLs, include them in the answer. If the answer is not
    found in the context, respond with "Nothing found in the documentation."

    Never fabricate answers or URLs.
    """

    question: str = udspy.InputField()
    context: dict[str, str] = udspy.InputField(
        desc="A mapping of source URLs to content."
    )

    answer: str = udspy.OutputField()
    sources: list[str] = udspy.OutputField(
        desc=(
            "A list of source URLs as strings used to generate the answer, "
            "picked from the provided context keys, in order of importance."
        )
    )
    reliability: float = udspy.OutputField(
        desc=(
            "The reliability score of the answer, from 0 to 1. "
            "1 means the answer is fully supported by the provided context. "
            "0 means the answer is not supported by the provided context."
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
    Returns a function that searches the Baserow documentation for a given query.
    """

    async def search_user_docs(
        question: Annotated[
            str, "The English version of the user question, using Baserow vocabulary."
        ]
    ) -> dict[str, Any]:
        """
        Search Baserow documentation to provide instructions and information for USERS.

        This tool provides end-user documentation explaining Baserow features and how
        users can use them manually through the UI. It does NOT contain information
        about:
        - Which tools/functions the agent should use
        - How to use agent tools or loaders
        - Agent-specific implementation details

        Use this ONLY when the user explicitly asks for instructions on how to do
        something themselves, or wants to learn about Baserow features.

        Make sure the question is in English and uses Baserow-specific terminology
        to get the best results.
        """

        nonlocal tool_helpers

        tool_helpers.update_status(_("Exploring the knowledge base..."))

        @sync_to_async
        def _search(question: str) -> list[KnowledgeBaseChunk]:
            chunks = KnowledgeBaseHandler().search(question)
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

        # If for any reason the model wasn't able to return sources correctly, fill them
        # from the available URLs.
        if not sources:
            sources = list(available_urls)

        return {
            "answer": prediction.answer,
            "reliability": prediction.reliability,
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
