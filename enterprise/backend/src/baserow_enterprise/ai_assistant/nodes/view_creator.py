"""
Node for creating Baserow views.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, VisualizationMessage


class ViewCreatorNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Creates Baserow views with filters and sorts."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Generate view creation query."""
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a Baserow view creator. Generate a JSON schema for creating a view based on the user's request.

The schema should include:
- view_name: string
- type: one of (grid, gallery, form, kanban)
- filters: array of filter objects, each with:
  - field: field name
  - type: filter type (equal, not_equal, contains, greater_than, etc.)
  - value: filter value
- sorts: array of sort objects, each with:
  - field: field name  
  - order: asc or desc

Return ONLY valid JSON.""",
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": user_message})

        try:
            view_schema = json.loads(response.content)

            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "create_view", "schema": view_schema}
                    )
                ],
                current_query=view_schema,
            )
        except json.JSONDecodeError:
            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "create_view", "raw": response.content}
                    )
                ],
                error_message="Failed to parse view schema",
            )
