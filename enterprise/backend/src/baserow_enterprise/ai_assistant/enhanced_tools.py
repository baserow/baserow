"""
Enhanced tool node that can create visualization messages from tool artifacts
"""

from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from baserow_enterprise.ai_assistant.tools.documentation_lookup import (
    DocumentationLookupArtifact,
)

from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt
from baserow_enterprise.ai_assistant.visualization_wrapper import (
    create_table_navigation_message,
    create_visualization_message,
)
from baserow_enterprise.ai_assistant.tools.table_finder import (
    TableFinderTool,
    TableFinderToolArtifact,
    TableFinderToolTableItem,
)
from django.conf import settings


class EnhancedToolNode:
    """
    Enhanced tool node that processes tool results and creates visualization messages.
    """

    def __init__(self, tools: List):
        self.tools = tools
        self.base_tool_node = ToolNode(tools)

    async def __call__(self, state: Dict, config: RunnableConfig) -> Dict[str, Any]:
        # Get the tool calls from the last message
        last_message = state["messages"][-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}

        tool_messages = []
        visualization_messages = []
        latest_action_is_undoable = False

        # Process each tool call
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            # Find and execute the tool
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if not tool:
                tool_messages.append(
                    ToolMessage(
                        content=f"Tool {tool_name} not found",
                        tool_call_id=tool_id,
                    )
                )
                continue

            try:
                # Execute the tool
                result = await tool.ainvoke(tool_call, config)
                additional_kwargs = {}

                if result.artifact:
                    if "latest_action_is_undoable" in result.artifact:
                        latest_action_is_undoable = result.artifact[
                            "latest_action_is_undoable"
                        ]

                    # Create visualization message if applicable
                    if isinstance(result.artifact, TableFinderToolArtifact):
                        viz_message = self._create_table_navigation_visualization(
                            result.artifact, tool_id
                        )
                        # Interrupt the current flow with the visualization message
                        interrupt(viz_message)
                    elif (
                        "navigate" in result.artifact
                        and len(last_message.tool_calls) == 1
                    ):
                        nav_message = self.create_navigation_message(
                            result.artifact, tool_id
                        )
                        interrupt(nav_message)
                    elif isinstance(result.artifact, DocumentationLookupArtifact):
                        tool_messages.append(
                            ToolMessage(
                                content="Documentation: %s"
                                % "\n\n - ".join(
                                    res.content for res in result.artifact.results
                                ),
                                tool_call_id=tool_id,
                            )
                        )
                    else:
                        tool_messages.append(
                            ToolMessage(
                                content=str(result.content),
                                tool_call_id=tool_id,
                                additional_kwargs=additional_kwargs,
                            )
                        )

                else:
                    # Regular tool result (just a string)
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        )
                    )
            except Exception as e:
                if isinstance(e, GraphInterrupt):
                    raise

                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool {tool_name}: {str(e)}",
                        tool_call_id=tool_id,
                    )
                )

        # Combine all messages
        all_messages = tool_messages + visualization_messages
        return {
            "messages": all_messages,
            "latest_action_is_undoable": latest_action_is_undoable,
        }

    def create_navigation_message(self, artifact, tool_id: str):
        """
        Create a visualization message for table navigation.
        """
        tables_data = []
        content = "| ID  | Table Name       | Database Name    |\n"
        content += "|-----|------------------|------------------|\n"

        dst = artifact["navigate"]

        table_data = {
            "id": dst["table_id"],
            "name": dst["table_name"],
            "view_id": dst.get("view_id"),
            "view_name": dst.get("view_name"),
            "database_id": dst["database_id"],
            "database_name": dst["database_name"],
            "navigation_url": f"/database/{dst['database_id']}/table/{dst['table_id']}/{dst.get('view_id', '')}",
        }
        tables_data.append(table_data)
        content += f"| {dst['table_id']} | [{dst['table_name']}]({table_data['navigation_url']}) | {table_data['database_name']} |\n"

        viz_message = create_table_navigation_message(
            content, tables_data, tool_call_id=tool_id
        )
        return viz_message

    def _create_table_navigation_visualization(
        self,
        artifact: TableFinderToolArtifact,
        tool_id: str,
    ):
        """
        Create a visualization message for table navigation.
        """
        tables_data = []
        content = "| ID  | Table Name       | Database Name    |\n"
        content += "|-----|------------------|------------------|\n"

        for table in artifact.tables:
            table_data = {
                "id": table.id,
                "name": table.name,
                "database_id": table.database_id,
                "database_name": table.database_name,
                "created_on": (
                    table.created_on.isoformat()
                    if hasattr(table.created_on, "isoformat")
                    else str(table.created_on)
                ),
                # Add navigation URL or path
                "navigation_url": f"/database/{table.database_id}/table/{table.id}",
            }
            tables_data.append(table_data)
            content += f"| {table.id} | [{table.name}]({table_data['navigation_url']}) | {table_data['database_name']} |\n"

        viz_message = create_table_navigation_message(
            content, tables_data, tool_call_id=tool_id
        )
        return viz_message

    def _get_ui_instructions(self, action: str, table_count: int) -> str:
        """Get user-friendly instructions for the UI."""
        if action == "no_tables_found":
            return "No tables found matching your search criteria. Try adjusting your search terms."
        elif action == "navigate_to_single_table":
            return "Found one table. Click below to navigate to it."
        elif action == "show_table_selector":
            return (
                f"Found {table_count} tables. Select the one you want to navigate to."
            )
        else:
            return "Table search completed."


def create_enhanced_tool_node_with_fallback(tools: List) -> EnhancedToolNode:
    """
    Create an enhanced tool node with error handling.
    """
    from langchain_core.runnables import RunnableLambda
    from .all_in_one import handle_tool_error

    enhanced_node = EnhancedToolNode(tools)

    # Wrap with error handling
    def wrapped_node(state, config=None):
        try:
            return enhanced_node(state, config or {})
        except Exception as e:
            return handle_tool_error({"error": e, **state})

    return RunnableLambda(wrapped_node)
