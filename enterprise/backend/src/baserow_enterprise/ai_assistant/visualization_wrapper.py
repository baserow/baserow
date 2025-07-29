"""
Wrapper to create LangChain-compatible visualization messages
"""

from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage, ToolMessage
import json
import uuid


def create_table_navigation_message(content, tables, tool_call_id):
    """
    Create a table navigation message for the given tables.
    """
    return ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
        additional_kwargs={
            "visualization": {
                "type": "table_navigation",
                "tables": tables,
            },
            "message_type": "visualization",
        },
    )


def create_visualization_message(
    query: Dict[str, Any], answer: Optional[Dict[str, Any]] = None, **kwargs
) -> AIMessage:
    """
    Create a LangChain-compatible visualization message using AIMessage.

    This wraps the visualization data in an AIMessage with structured content
    that the frontend can recognize and process.
    """

    visualization_data = {
        "type": "visualization",
        "query": query,
        "answer": answer or {},
        "id": kwargs.get("id", str(uuid.uuid4())),
    }

    # Create readable content for the AI message
    content = kwargs.pop("content", _create_readable_content(query, answer))

    # Store visualization data in additional_kwargs for frontend access
    return AIMessage(
        content=content,
        additional_kwargs={
            "visualization": visualization_data,
            "message_type": "visualization",
        },
        **kwargs,
    )


def _create_readable_content(
    query: Dict[str, Any], answer: Optional[Dict[str, Any]]
) -> str:
    """Create human-readable content from visualization data."""

    viz_type = query.get("type", "unknown")

    if viz_type == "table_navigation":
        tables_count = query.get("tables_found_count", 0)
        if tables_count == 0:
            return "No tables found matching your criteria."
        elif tables_count == 1:
            table_name = answer.get("selected_table", {}).get("name", "table")
            return f"Found table '{table_name}'. Click to navigate to it."
        else:
            return f"Found {tables_count} tables. Select one to navigate to it."

    elif viz_type == "table_search":
        return f"Table search completed with {query.get('results_count', 0)} results."

    else:
        return f"Visualization of type '{viz_type}' completed."


def extract_visualization_data(message: AIMessage) -> Optional[Dict[str, Any]]:
    """
    Extract visualization data from an AIMessage.

    Returns None if the message doesn't contain visualization data.
    """
    if not hasattr(message, "additional_kwargs"):
        return None

    return message.additional_kwargs.get("visualization")


def is_visualization_message(message: AIMessage) -> bool:
    """Check if a message contains visualization data."""
    return extract_visualization_data(message) is not None
