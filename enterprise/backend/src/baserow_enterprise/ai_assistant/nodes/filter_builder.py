"""
Node for building Baserow filters.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, VisualizationMessage


class FilterBuilderNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Builds filter configurations for Baserow views."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Generate filter configuration."""
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a Baserow filter builder. Generate a JSON filter configuration based on the user's request.

Filter types available:
- equal, not_equal
- contains, not_contains
- higher_than, lower_than
- is_empty, not_empty
- date_equals, date_before, date_after

The schema should be:
{
  "filters": [
    {
      "field": "field_name",
      "type": "filter_type",
      "value": "filter_value"
    }
  ],
  "filter_type": "AND" or "OR"
}

Return ONLY valid JSON.""",
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": user_message})

        try:
            filter_config = json.loads(response.content)

            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "filter", "config": filter_config}
                    )
                ],
                current_query=filter_config,
            )
        except json.JSONDecodeError:
            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "filter", "raw": response.content}
                    )
                ],
                error_message="Failed to parse filter configuration",
            )
