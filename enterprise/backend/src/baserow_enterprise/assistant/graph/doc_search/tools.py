from typing import Any
from baserow_enterprise.assistant.graph.doc_search.handler import DocSearchHandler
from baserow_enterprise.assistant.graph.doc_search.prompts import (
    COMPRESS_SEARCH_DOCUMENTS_PROMPT,
)
from baserow_enterprise.assistant.types import THINKING_MESSAGES, AiThinkingMessage
from .types import DocSearchArtifact, DocSearchToolArgsSchema
from baserow_enterprise.assistant.graph.tool import AssistantBaseTool
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.config import get_stream_writer


class DocSearchTool(AssistantBaseTool):
    name: str = "search_docs"
    description: str = """
Search comprehensive Baserow documentation for features, tutorials, API references, and how-to guides. 
    
This tool contains detailed information about:
- All Baserow features and capabilities
- Step-by-step tutorials and setup guides  
- Field types, formulas, and advanced configurations
- Integration guides and best practices

Always use this tool when users ask about Baserow functionality, features, or implementation details.
"""
    args_schema: type[BaseModel] = DocSearchToolArgsSchema

    def _run_impl(self, enhanced_question: str, **kwargs) -> tuple[str, Any]:
        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(content=THINKING_MESSAGES.SEARCHING_DOCS))

        relevant_docs = DocSearchHandler().search_documents(enhanced_question)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMPRESS_SEARCH_DOCUMENTS_PROMPT),
            ],
            template_format="mustache",
        )
        llm = self._get_model()
        chain = prompt | llm
        response: DocSearchArtifact = chain.invoke(
            {
                "relevant_docs": relevant_docs,
                "user_question": enhanced_question,
            }
        )
        return response.search_result, response

    def _get_model(self, model: str = None):
        return init_chat_model(
            model=model or "openai:gpt-4.1-nano",
            temperature=0.3,
            disable_streaming=True,
        ).with_structured_output(DocSearchArtifact)
