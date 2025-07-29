"""
Main Baserow Assistant orchestrator.
"""
from copy import copy
from typing import Optional, AsyncGenerator
from uuid import uuid4
from langchain_core.runnables import RunnableConfig

from baserow_enterprise.ai_assistant.all_in_one import State

from .graph.graph import AssistantGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from .utils.types import (
    AssistantState,
    HumanMessage,
    AnyAssistantMessage,
    AssistantNodeName,
)
from langchain_core.messages import AIMessage
from .models import AssistantChat
from django.contrib.auth.models import AbstractUser


class BaserowAssistant:
    """Main assistant class that orchestrates the graph execution."""

    def __init__(
        self,
        user: AbstractUser,
        workspace: Optional[int] = None,
        chat: Optional[AssistantChat] = None,
        new_message: Optional[str] = None,
        context=None,
        checkpointer: Optional[
            AsyncPostgresSaver
        ] = None,  # TODO: this should not be passed to the assistant
    ):
        self.user = user
        self.workspace = workspace
        self.chat = chat
        self.context = context or {}
        self.thread_id = str(chat.uid or uuid4())
        self._latest_message = (
            HumanMessage(content=new_message, id=str(uuid4())) if new_message else None
        )

        self._assistant = AssistantGraph(user, workspace, context=context)
        self._graph = None
        self.checkpointer = checkpointer

        self._state = None

    async def ainvoke(self) -> list[AnyAssistantMessage]:
        """Process a message and return all responses at once."""
        messages = []

        async for msg in self.astream():
            messages.append(msg)

        return messages

    def get_config(self) -> RunnableConfig:
        config: RunnableConfig = {
            "configurable": {
                "thread_id": self.thread_id,
                "user": self.user,
                "chat": self.chat,
                "workspace": self.workspace,
            }
        }
        return config

    async def aget_graph(self):
        if not self._graph:
            self._graph = await self._assistant.compile_full_graph(
                checkpointer=self.checkpointer
            )
        return self._graph

    async def _init_state(self):
        config = self.get_config()
        graph = await self.aget_graph()
        snapshot = await graph.aget_state(config)

        # If the graph previously hasn't reset the state, it is an interrupt. We resume from the point of interruption.
        if snapshot.next and self._latest_message:
            tool_messages = []
            for interrupt in snapshot.interrupts:
                if (
                    "visualization" in interrupt.value.additional_kwargs
                ):  # the latest_message is a new message, just save the result as a toolmessage
                    tool_messages.append(interrupt.value)
                    if self._latest_message.content == "navigation done":
                        return None
                else:  # the latest_message is the answer to the interrupt, so we want to use it to resume the graph with Command(resume=...)
                    pass  # TODO

            if tool_messages:
                await graph.aupdate_state(
                    config, AssistantState(messages=tool_messages)
                )

        if self._latest_message:
            initial_state = AssistantState(
                messages=[self._latest_message],
                start_id=self._latest_message.id,
                graph_status=None,
            )
        else:
            initial_state = AssistantState(messages=[])
        return initial_state

    async def astream(self) -> AsyncGenerator[AnyAssistantMessage, None]:
        """Stream responses for a message."""

        # Create config with chat UID as thread ID
        config = self.get_config()
        state = await self._init_state()
        graph = await self.aget_graph()

        # Stream through the graph
        async for update in graph.astream(state, config=config, stream_mode=["values"]):
            # Extract new messages from updates
            # Handle both tuple format ('values', data) and direct dict format
            update_data = (
                update[1]
                if isinstance(update, tuple) and update[0] == "values"
                else update
            )

            if not self.chat.title and update_data.get("title"):
                self.chat.title = update_data["title"]
                await self.chat.asave(update_fields=["title"])

            self.chat.latest_action_is_undoable = update_data.get(
                "latest_action_is_undoable"
            )

            if "messages" in update_data:
                # Get the last message that was added
                new_messages = update_data["messages"]
                found = False
                for msg in new_messages:
                    if found and msg.content:
                        yield msg
                    if msg.id == self._latest_message.id:
                        found = True

        # Check if the assistant has requested help.
        state = await self._graph.aget_state(config)
        if state.next:
            interrupt_messages = []
            for task in state.tasks:
                for interrupt in task.interrupts:
                    interrupt_message = (
                        AIMessage(content=interrupt.value, id=str(uuid4()))
                        if isinstance(interrupt.value, str)
                        else interrupt.value
                    )
                    interrupt_messages.append(interrupt_message)
                    yield interrupt_message

            # await self._graph.aupdate_state(
            #     config,
            #     AssistantState(
            #         messages=interrupt_messages,
            #         # LangGraph by some reason doesn't store the interrupt exceptions in checkpoints.
            #         graph_status="interrupted",
            #     ),
            # )
