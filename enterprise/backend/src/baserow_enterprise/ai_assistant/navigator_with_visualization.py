"""
Enhanced navigator that returns visualization messages for table navigation
"""

from typing import Dict, List, Optional, Tuple
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from baserow_enterprise.ai_assistant.utils.types import VisualizationMessage
from baserow_enterprise.ai_assistant.tools.table_finder import (
    TableFinderTool,
    TableFinderToolArtifact,
)


class NavigatorWithVisualization:
    """
    Custom navigator assistant that processes table finder results
    and returns visualization messages for frontend navigation.
    """

    def __init__(self, runnable, tools):
        self.runnable = runnable
        self.tools = tools
        self.tool_node = ToolNode(tools)

    async def __call__(self, state: dict, config: RunnableConfig) -> dict:
        """
        Process the state and return visualization messages when tables are found.
        """
        # First, let the LLM decide what to do (call tools or respond)
        result = await self.runnable.ainvoke(state, config)

        # Check if the LLM wants to call the table finder tool
        if result.tool_calls:
            # Execute the tool calls
            tool_messages = []
            visualization_messages = []

            for tool_call in result.tool_calls:
                if tool_call["name"] == "table_finder":
                    # Execute the table finder tool
                    tool = next(t for t in self.tools if t.name == "table_finder")
                    tool_result = await tool.ainvoke(tool_call["args"], config)

                    # Extract the artifact if available
                    if isinstance(tool_result, tuple) and len(tool_result) == 2:
                        message, artifact = tool_result

                        if isinstance(artifact, TableFinderToolArtifact):
                            # Create a visualization message for the frontend
                            viz_message = self._create_table_navigation_visualization(
                                artifact, tool_call["args"]
                            )
                            visualization_messages.append(viz_message)

                        # Also create a tool message for the conversation
                        tool_messages.append(
                            ToolMessage(
                                content=message,
                                tool_call_id=tool_call["id"],
                            )
                        )
                else:
                    # For other tools, execute normally
                    # This is a simplified version - you'd need proper tool execution
                    tool_messages.append(
                        ToolMessage(
                            content=f"Executed {tool_call['name']}",
                            tool_call_id=tool_call["id"],
                        )
                    )

            # Return both the tool messages and visualization messages
            messages = []

            # Add the AI message with tool calls first
            messages.append(result)

            # Add tool messages
            messages.extend(tool_messages)

            # Add visualization messages if any
            messages.extend(visualization_messages)

            # Add a summary message
            if visualization_messages:
                summary = self._create_navigation_summary(visualization_messages[0])
                messages.append(AIMessage(content=summary))

            return {"messages": messages}
        else:
            # No tool calls, just return the LLM response
            return {"messages": result}

    def _create_table_navigation_visualization(
        self, artifact: TableFinderToolArtifact, search_params: dict
    ) -> VisualizationMessage:
        """
        Create a visualization message for table navigation.
        """
        tables_data = []
        for table in artifact.tables:
            tables_data.append(
                {
                    "id": table.id,
                    "name": table.name,
                    "database_id": table.database_id,
                    "database_name": table.database_name,
                    "created_on": table.created_on.isoformat()
                    if hasattr(table.created_on, "isoformat")
                    else str(table.created_on),
                }
            )

        return VisualizationMessage(
            query={
                "type": "navigate_to_table",
                "search_params": search_params,
                "tables_found": len(tables_data),
            },
            answer={
                "tables": tables_data,
                "action": "show_table_selector"
                if len(tables_data) > 1
                else "navigate_to_table",
                "selected_table_id": tables_data[0]["id"]
                if len(tables_data) == 1
                else None,
            },
        )

    def _create_navigation_summary(self, viz_message: VisualizationMessage) -> str:
        """
        Create a human-readable summary of the navigation action.
        """
        tables_count = viz_message.query.get("tables_found", 0)

        if tables_count == 0:
            return "No tables found matching your criteria."
        elif tables_count == 1:
            table = viz_message.answer["tables"][0]
            return f"Found table '{table['name']}' in database '{table['database_name']}'. Click to navigate to this table."
        else:
            return f"Found {tables_count} tables matching your criteria. Please select which table you'd like to navigate to."


def create_enhanced_navigator_node():
    """
    Factory function to create an enhanced navigator node for the graph.
    """
    from .all_in_one import navigator_runnable, navigator_tools

    return NavigatorWithVisualization(
        runnable=navigator_runnable, tools=navigator_tools
    )


# Alternative: Wrapper function that processes tool results
async def process_navigator_tool_results(state: dict) -> dict:
    """
    Process tool results from the navigator and create visualization messages.
    This can be used as an intermediate node after navigator_tools.
    """
    messages = state.get("messages", [])

    if not messages:
        return state

    last_message = messages[-1]

    # Check if the last message is a ToolMessage from table_finder
    if isinstance(last_message, ToolMessage):
        # Parse the tool message to extract table information
        # This is a simplified version - you'd need to properly extract the artifact

        # For now, create a mock visualization message
        # In reality, you'd extract this from the tool execution context
        viz_message = VisualizationMessage(
            query={
                "type": "table_search_completed",
                "tool_call_id": last_message.tool_call_id,
            },
            answer={
                "status": "success",
                "message": last_message.content,
                # Add extracted table data here
            },
        )

        return {"messages": [viz_message]}

    return state
