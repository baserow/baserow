"""
Node for creating or modifying Baserow tables.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, VisualizationMessage


class TableCreatorNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Creates or modifies Baserow tables."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Generate table creation query."""
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a Baserow table creator. Generate a JSON schema for creating a table based on the user's request.

The schema should include:
- table_name: string
- fields: array of field objects, each with:
  - name: string
  - type: one of (text, number, boolean, date, single_select, multiple_select, link_row, formula)
  - options: optional configuration for the field type

Return ONLY valid JSON.""",
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": user_message})

        try:
            # Parse the JSON response
            table_schema = json.loads(response.content)

            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "create_table", "schema": table_schema}
                    )
                ],
                current_query=table_schema,
            )
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return PartialAssistantState(
                messages=[
                    VisualizationMessage(
                        query={"type": "create_table", "raw": response.content}
                    )
                ],
                error_message="Failed to parse table schema",
            )
