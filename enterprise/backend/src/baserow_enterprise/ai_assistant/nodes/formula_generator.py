"""
Node for generating Baserow formulas.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, VisualizationMessage


class FormulaGeneratorNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Generates Baserow formula expressions."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Generate formula expression."""
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a Baserow formula expert. Generate formula expressions based on the user's request.

Baserow supports formulas similar to spreadsheets with functions like:
- Math: sum(), avg(), min(), max(), round()
- Text: concat(), upper(), lower(), trim()
- Date: date_diff(), date_format(), today()
- Logical: if(), and(), or(), not()
- Field references: field('field_name')

Generate the formula expression and explain what it does.""",
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": user_message})

        # Extract formula from response (simple approach)
        lines = response.content.split("\n")
        formula = ""
        explanation = response.content

        for line in lines:
            if "=" in line or "field(" in line.lower():
                formula = line.strip()
                break

        return PartialAssistantState(
            messages=[
                VisualizationMessage(
                    query={
                        "type": "formula",
                        "expression": formula or response.content,
                        "explanation": explanation,
                    }
                )
            ],
            current_query={"formula": formula, "explanation": explanation},
        )
