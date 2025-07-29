"""
Fixed Assistant class that handles message type conversion
"""

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import HumanMessage as LangChainHumanMessage
from typing import Union
from message_converter import MessageAdapter


class AssistantFixed:
    """
    Assistant that handles conversion between Baserow and LangChain message types.
    """
    
    def __init__(self, runnable: Runnable):
        self.runnable = runnable
        self.adapter = MessageAdapter()

    async def __call__(self, state: dict, config: RunnableConfig):
        """
        Process state with message type conversion.
        """
        while True:
            # Convert Baserow messages to LangChain format before invoking
            langchain_state = self.adapter.prepare_state_for_langchain(state)
            
            # Invoke the runnable with converted messages
            result = await self.runnable.ainvoke(langchain_state, config)
            
            # Check if we got a valid response
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                # Add a prompt for real output
                new_message = LangChainHumanMessage(content="Respond with a real output.")
                langchain_state["messages"] = langchain_state["messages"] + [new_message]
                state = langchain_state  # Update state for next iteration
            else:
                break
        
        # Return the result (keep as LangChain format for now, 
        # conversion can happen at the graph level if needed)
        return {"messages": result}


# Alternative: Minimal fix for existing Assistant class
def fix_existing_assistant(original_assistant_class):
    """
    Monkey patch or wrap the existing Assistant class to handle message conversion.
    """
    original_call = original_assistant_class.__call__
    
    async def new_call(self, state: dict, config: RunnableConfig):
        # Convert messages if needed
        if "messages" in state and state["messages"]:
            from langchain_core.messages import BaseMessage
            
            # Check if first message is not a LangChain message
            if state["messages"] and not isinstance(state["messages"][0], BaseMessage):
                from message_converter import convert_messages_for_langchain
                state = {
                    **state,
                    "messages": convert_messages_for_langchain(state["messages"])
                }
        
        # Call original method
        return await original_call(self, state, config)
    
    original_assistant_class.__call__ = new_call
    return original_assistant_class