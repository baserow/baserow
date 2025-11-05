from typing import TYPE_CHECKING, Annotated, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

import udspy

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType

from .handler import KnowledgeBaseHandler

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers

MAX_SOURCES = 3


class SearchDocsSignature(udspy.Signature):
    """
    Search the Baserow documentation for relevant information to answer user questions.
    Never fabricate answers or URLs. Always copy instructions exactly as they appear in
    the documentation, without rephrasing.
    """

    question: str = udspy.InputField()
    context: list[str] = udspy.InputField()
    response: str = udspy.OutputField()
    sources: list[str] = udspy.OutputField(
        desc=f"List of unique and relevant source URLs. Max {MAX_SOURCES}."
    )
    reliability: float = udspy.OutputField(
        desc=(
            "The reliability score of the response, from 0 to 1. "
            "1 means the answer is fully supported by the provided context. "
            "0 means the answer is not supported by the provided context."
        )
    )


class SearchDocsRAG(udspy.Module):
    def __init__(self):
        self.rag = udspy.ChainOfThought(SearchDocsSignature)

    def forward(self, question: str, *args, **kwargs):
        context = KnowledgeBaseHandler().search(question, num_results=10)
        return self.rag(context=context, question=question)


def get_search_docs_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[str], dict[str, Any]]:
    """
    Returns a function that searches the Baserow documentation for a given query.
    """

    def search_docs(
        question: Annotated[
            str, "The English version of the user question, using Baserow vocabulary."
        ]
    ) -> dict[str, Any]:
        """
        Search Baserow documentation for relevant information. Make sure the question
        is in English and uses Baserow-specific terminology to get the best results.
        """

        nonlocal tool_helpers

        tool_helpers.update_status(_("Exploring the knowledge base..."))

        search_tool = SearchDocsRAG()
        answer = search_tool(question=question)
        # Somehow sources can be objects with an "url" attribute instead of strings,
        # let's fix that
        fixed_sources = []
        for src in answer.sources[:MAX_SOURCES]:
            if isinstance(src, str):
                fixed_sources.append(src)
            elif isinstance(src, dict) and "url" in src:
                fixed_sources.append(src["url"])

        return {
            "response": answer.response,
            "sources": fixed_sources,
            "reliability": answer.reliability,
        }

    return search_docs


class SearchDocsToolType(AssistantToolType):
    type = "search_docs"

    def can_use(
        self, user: AbstractUser, workspace: Workspace, *args, **kwargs
    ) -> bool:
        return KnowledgeBaseHandler().can_search()

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_search_docs_tool(user, workspace, tool_helpers)
