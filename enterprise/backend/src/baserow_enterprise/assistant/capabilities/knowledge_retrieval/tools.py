from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from pydantic import BaseModel

from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool
from baserow_enterprise.assistant.types import THINKING_MESSAGES, AiThinkingMessage

from .handler import KnowledgeBaseHandler
from .prompts import (
    RETRIEVE_KNOWLEDGE_TOOL_PROMPT,
    RETRIEVE_KNOWLEDGE_TOOL_USAGE_INSTRUCTIONS,
)
from .types import KnowledgeToolArgsSchema, KnowledgeToolArtifact


class RetrieveKnowledgeTool(AssistantBaseTool):
    name: str = "retrieve_knowledge"
    description: str = (
        "Retrieve relevant knowledge from Baserow's documentation: user guides, "
        "API references, tutorials, and FAQs."
    )
    usage_instructions: str = RETRIEVE_KNOWLEDGE_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = KnowledgeToolArgsSchema

    def _run_impl(self, query: str, **kwargs) -> tuple[str, Any]:
        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.RETRIEVE_KNOWLEDGE))

        relevant_chunks = KnowledgeBaseHandler().retrieve_knowledge_chunks(query)

        # Provide intermediate feedback while processing the retrieved knowledge
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.ANALYZE_KNOWLEDGE))

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RETRIEVE_KNOWLEDGE_TOOL_PROMPT),
            ],
            template_format="mustache",
        )
        llm = self._get_model().with_structured_output(KnowledgeToolArtifact)
        chain = prompt | llm
        response: KnowledgeToolArtifact = chain.invoke(
            {
                "relevant_knowledge_chunks": "\n\n".join(relevant_chunks),
                "user_question": query,
            }
        )

        return response.knowledge, response

    def _get_model(self, model: str = None):
        return init_chat_model(
            model=model or "openai:gpt-4.1-nano",
            temperature=0.3,
        )

    def can_be_used(self, config: RunnableConfig) -> bool:
        return KnowledgeBaseHandler().has_knowledge()
