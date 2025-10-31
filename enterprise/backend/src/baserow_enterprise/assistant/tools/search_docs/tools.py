from typing import TYPE_CHECKING, Any, Callable, TypedDict

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
    question: str = udspy.InputField()
    context: list[str] = udspy.InputField()
    response: str = udspy.OutputField()
    sources: list[str] = udspy.OutputField(
        desc=f"List of unique and relevant source URLs. Max {MAX_SOURCES}."
    )


class SearchDocsRAG(udspy.Module):
    def __init__(self):
        self.respond = SearchDocsSignature

    def forward(self, question):
        context = KnowledgeBaseHandler().search(question, num_results=10)
        return self.respond(context=context, question=question)


class SearchDocsToolOutput(TypedDict):
    response: str
    sources: list[str]


def get_search_docs_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[str], SearchDocsToolOutput]:
    """
    Returns a function that searches the Baserow documentation for a given query.
    """

    def search_docs(query: str) -> SearchDocsToolOutput:
        """
        Search Baserow documentation.
        """

        nonlocal tool_helpers

        tool_helpers.update_status(_("Exploring the knowledge base..."))

        tool = SearchDocsRAG()
        result = tool(query)

        sources = []
        for source in result.sources:
            if source not in sources:
                sources.append(source)
            if len(sources) >= MAX_SOURCES:
                break

        return SearchDocsToolOutput(
            response=result.response,
            sources=sources,
        )

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
