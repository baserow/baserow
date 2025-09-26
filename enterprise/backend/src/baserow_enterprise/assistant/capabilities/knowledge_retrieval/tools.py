import os
from typing import Annotated, Any

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from pydantic import BaseModel
from langgraph.types import Command
from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool
from baserow_enterprise.assistant.types import (
    THINKING_MESSAGES,
    AiThinkingMessage,
    PartialAssistantState,
    ToolCallMessage,
)
from baserow_enterprise.assistant.utils.retry_utils import invoke_with_retry
from langchain_core.tools import InjectedToolCallId
from .handler import KnowledgeBaseHandler
from .prompts import (
    RETRIEVE_KNOWLEDGE_TOOL_PROMPT,
    RETRIEVE_KNOWLEDGE_TOOL_USAGE_INSTRUCTIONS,
)
from .types import RetrieveKnowledgeToolArgsSchema, RetrieveKnowledgeToolArtifact


class RetrieveKnowledgeTool(AssistantBaseTool):
    name: str = "retrieve_knowledge"
    description: str = (
        "Retrieve relevant knowledge from Baserow's documentation: user guides, "
        "API references, tutorials, and FAQs."
    )
    usage_instructions: str = RETRIEVE_KNOWLEDGE_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = RetrieveKnowledgeToolArgsSchema

    def _run_impl(
        self, query: str, tool_call_id: Annotated[str, InjectedToolCallId], **kwargs
    ) -> tuple[str, Any]:
        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.RETRIEVE_KNOWLEDGE))

        relevant_chunks = KnowledgeBaseHandler().search(query, num_results=10)

        # Provide intermediate feedback while processing the retrieved knowledge
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.ANALYZE_KNOWLEDGE))

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RETRIEVE_KNOWLEDGE_TOOL_PROMPT),
            ],
            template_format="mustache",
        )
        llm = self._get_model().with_structured_output(
            RetrieveKnowledgeToolArtifact, method="json_schema"
        )
        chain = prompt | llm

        # Use retry logic for robust parsing
        result: RetrieveKnowledgeToolArtifact = invoke_with_retry(
            lambda: chain.invoke(
                {
                    "user_question": query,
                    "relevant_knowledge_chunks": "\n\n".join(relevant_chunks),
                }
            )
        )

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=result.knowledge,
                        artifact=result,
                    )
                ],
                sources=result.sources,
            )
        )

    def _get_model(self):
        # from langchain_openai import ChatOpenAI

        # return ChatOpenAI(
        #     model_name="openai.gpt-oss-120b-1:0",
        #     temperature=0,
        #     streaming=True,
        #     api_key=os.environ["BEDROCK_API_KEY"],
        #     base_url="https://bedrock-runtime.eu-west-1.amazonaws.com/openai/v1",
        #     # output_version="responses/v1",
        # )
        return init_chat_model(
            "groq:openai/gpt-oss-120b",
            temperature=0,
            max_retries=3,
        )

    def can_be_used(self) -> bool:
        return KnowledgeBaseHandler().can_search()
