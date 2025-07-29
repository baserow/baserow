"""
Message filtering to return only final user-facing messages
"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, BaseMessage
from baserow_enterprise.ai_assistant.visualization_wrapper import (
    is_visualization_message,
    extract_visualization_data,
)


class MessageFilter:
    """
    Filter messages to return only the final user-facing content.
    """
    
    INTERNAL_MESSAGES = [
        "The assistant is now the",
        "Navigator assistant",
        "View expert assistant", 
        "Reflect on the above conversation",
        "Use the provided tools",
        "Resuming dialog with the host assistant",
        "Found 2 tables matching the criteria",  # Tool result message
        "actions are not complete until after you have successfully invoked",
    ]
    
    @staticmethod
    def filter_final_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Filter messages to return only the final user-facing messages.
        
        Priority order:
        1. Visualization messages (highest priority)
        2. Final AI response (if no visualization)
        3. Error messages (if any)
        """
        if not messages:
            return []
        
        # Find visualization messages
        visualization_messages = [
            msg for msg in messages 
            if isinstance(msg, AIMessage) and is_visualization_message(msg)
        ]
        
        # If we have visualization messages, return only those
        if visualization_messages:
            return visualization_messages
        
        # Otherwise, find the final user-facing AI message
        final_ai_messages = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and MessageFilter._is_user_facing_message(msg):
                final_ai_messages.insert(0, msg)
                break
        
        return final_ai_messages
    
    @staticmethod
    def _is_user_facing_message(message: AIMessage) -> bool:
        """Check if a message is user-facing (not internal processing)."""
        content = str(message.content).strip()
        
        # Skip empty messages
        if not content:
            return False
        
        # Skip internal processing messages
        for internal_phrase in MessageFilter.INTERNAL_MESSAGES:
            if internal_phrase in content:
                return False
        
        # Skip tool result messages (usually start with "Found X tables")
        if content.startswith("Found ") and "matching the criteria" in content:
            return False
        
        return True
    
    @staticmethod
    def create_final_response(messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Create the final response structure for the frontend.
        """
        filtered_messages = MessageFilter.filter_final_messages(messages)
        
        if not filtered_messages:
            return {
                "type": "text_response",
                "content": "I apologize, but I couldn't process your request.",
                "visualization": None,
            }
        
        final_message = filtered_messages[0]
        
        # Check if it's a visualization message
        if isinstance(final_message, AIMessage) and is_visualization_message(final_message):
            viz_data = extract_visualization_data(final_message)
            return {
                "type": "visualization_response",
                "content": final_message.content,
                "visualization": viz_data,
            }
        
        # Regular text response
        return {
            "type": "text_response", 
            "content": final_message.content,
            "visualization": None,
        }


def create_response_filter_node():
    """
    Create a node that filters messages for the final response.
    """
    def filter_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Filter messages and prepare final response."""
        messages = state.get("messages", [])
        
        # Apply filtering
        filtered_messages = MessageFilter.filter_final_messages(messages)
        
        # Replace the messages with only the filtered ones
        return {
            "messages": filtered_messages,
            "final_response": MessageFilter.create_final_response(messages)
        }
    
    return filter_node


def add_final_message_only(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add only the final user-facing message to the response.
    This can be used as a final node in the graph.
    """
    messages = state.get("messages", [])
    
    # Find visualization messages first
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and is_visualization_message(msg):
            return {"messages": [msg]}
    
    # If no visualization, find the last user-facing AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and MessageFilter._is_user_facing_message(msg):
            return {"messages": [msg]}
    
    # Fallback: return empty or error message
    return {"messages": []}


# Custom streaming filter for real-time responses
class StreamingMessageFilter:
    """
    Filter streaming messages in real-time to avoid sending internal messages.
    """
    
    def __init__(self):
        self.message_buffer = []
        self.current_message_id = None
        self.skip_current_message = False
    
    def should_stream_content(self, content: str, message_id: str) -> bool:
        """
        Determine if content should be streamed to the user.
        """
        # New message started
        if message_id != self.current_message_id:
            self.current_message_id = message_id
            self.message_buffer = []
            self.skip_current_message = False
        
        # Add content to buffer
        self.message_buffer.append(content)
        full_content = "".join(self.message_buffer)
        
        # Check if we should skip this message
        for internal_phrase in MessageFilter.INTERNAL_MESSAGES:
            if internal_phrase in full_content:
                self.skip_current_message = True
                return False
        
        # If we're already skipping this message, continue skipping
        if self.skip_current_message:
            return False
        
        return True
    
    def is_final_message(self, content: str) -> bool:
        """Check if this is likely the final user-facing message."""
        # Look for patterns that indicate final responses
        final_patterns = [
            "tables. Select one to navigate",
            "Click to navigate to it",
            "No tables found",
            "Here are the results",
        ]
        
        for pattern in final_patterns:
            if pattern in content:
                return True
        
        return False