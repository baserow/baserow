from typing import Any, Callable, TypedDict

from django.contrib.auth.models import AbstractUser

import dspy
from dspy.dsp.utils.settings import settings as dspy_settings
from dspy.streaming.messages import sync_send_to_stream

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType
from baserow_enterprise.assistant.types import AiThinkingMessage

from .handler import KnowledgeBaseHandler

MAX_SOURCES = 3


class SearchDocsSignature(dspy.Signature):
    question: str = dspy.InputField()
    context: list[str] = dspy.InputField()
    response: str = dspy.OutputField()
    sources: list[str] = dspy.OutputField(
        description=f"List of unique and relevant source URLs. Max {MAX_SOURCES}."
    )


class SearchDocsToolOutput(TypedDict):
    response: str
    sources: list[str]


def search_docs(query: str) -> SearchDocsToolOutput:
    """
    Search Baserow documentation.

    **Critical**: Always use before answering specifics.
    Never use your general knowledge to answer specifics.

    Covers: user guides, API references, tutorials, FAQs, features, usage.
    """

    tool = SearchDocsRAG()
    result = tool(query)

    sources = []
    for source in result["sources"]:
        if source not in sources:
            sources.append(source)
        if len(sources) >= MAX_SOURCES:
            break

    return SearchDocsToolOutput(
        response=result["response"],
        sources=sources,
    )


class SearchDocsRAG(dspy.Module):
    def __init__(self):
        self.respond = dspy.ChainOfThought(SearchDocsSignature)

    def forward(self, question):
        context = KnowledgeBaseHandler().search(question, num_results=10)
        return self.respond(context=context, question=question)


class SearchDocsToolType(AssistantToolType):
    type = "search_docs"
    thinking_message = "Searching Baserow documentation..."

    def can_use(
        self, user: AbstractUser, workspace: Workspace, *args, **kwargs
    ) -> bool:
        return KnowledgeBaseHandler().can_search()

    def get_tool(self) -> Callable[[Any], Any]:
        return search_docs

    def on_tool_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ):
        stream = dspy_settings.send_stream
        if stream is not None:
            sync_send_to_stream(
                stream, AiThinkingMessage(code=self.type, content=self.thinking_message)
            )
