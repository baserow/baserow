"""
Query planning node that determines what operations to perform.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, AssistantMessage


class PlannerNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Plans the query execution strategy."""

    def router(self, state: AssistantState) -> str:
        """Route based on query type."""
        if not state.query_type:
            return "end"

        routing_map = {
            "table": "table",
            "view": "view",
            "formula": "formula",
            "filter": "filter",
            "execute": "execute",
        }

        return routing_map.get(state.query_type, "end")

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Plan the query execution."""
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a Baserow query planner. Analyze the request and determine:
1. What type of operation is needed (table, view, formula, filter)
2. What specific parameters are required
3. The execution order if multiple operations are needed

Respond with a structured plan.""",
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": user_message})

        # Determine query type from response
        response_lower = response.content.lower()
        if "table" in response_lower:
            query_type = "table"
        elif "view" in response_lower:
            query_type = "view"
        elif "formula" in response_lower:
            query_type = "formula"
        elif "filter" in response_lower:
            query_type = "filter"
        else:
            query_type = "execute"

        return PartialAssistantState(
            messages=[AssistantMessage(content=f"Query plan: {response.content}")],
            query_type=query_type,
            plan=response.content,
        )
