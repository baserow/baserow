from collections import defaultdict
from typing import Any, AsyncGenerator, AsyncIterator, Optional

from asgiref.sync import async_to_sync
from langchain_core.messages import AIMessageChunk
from langgraph.graph.state import CompiledStateGraph

from langchain_core.runnables.config import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.types import StreamMode, Command
from loguru import logger

from baserow_enterprise.assistant.graph import AssistantGraphBuilder

from .models import AssistantChat
from .types import (
    ASSISTANT_GRAPH_NODE,
    AiErrorMessage,
    AI_ERROR_MESSAGE_CODE,
    AiMessage,
    AiMessageChunk,
    AssistantExecutionContext,
    AssistantMessageUnion,
    AssistantState,
    ChatTitleMessage,
    HumanMessage,
)


def is_state_update(
    from_node: Optional[tuple[str]], update_type: str, update_value: Any
) -> bool:
    """
    Returns True if the update is an update of the assistant graph state.
    """

    return update_type == "values" and not from_node


def is_message_update(
    from_node: Optional[tuple[str]], update_type: str, update_value: Any
) -> bool:
    """
    Returns True if the update comes from a streaming update. This happens when the
    model defines streaming=True, so that every token is streamed as it is generated.
    """

    return update_type == "messages"


def validate_state_update(state_update: dict[Any, Any]) -> AssistantState:
    """
    Validate the state update against the AssistantState model.
    """

    return AssistantState.model_validate(state_update)


def get_message_by_node(
    node: ASSISTANT_GRAPH_NODE, **kwargs
) -> AssistantMessageUnion | None:
    """
    Returns the message associated with a specific node in the assistant graph.

    :param node: The node to get the message for.
    :param kwargs: Additional keyword arguments to pass to the message constructor.
    :return: The message associated with the specified node, or None if the node is not
        recognized.
    """

    if node == ASSISTANT_GRAPH_NODE.ROOT:
        return AiMessageChunk(content=kwargs.get("content", ""))
    elif node == ASSISTANT_GRAPH_NODE.TITLE_GENERATOR:
        return ChatTitleMessage(content=kwargs.get("content", ""))


def is_value_update(
    from_node: Optional[tuple[str]], update_type: str, update_value: Any
) -> bool:
    """
    Transition between nodes.
    """

    return update_type == "updates"


def is_interrupt(
    from_node: Optional[tuple[str]], update_type: str, update_value: Any
) -> bool:
    """
    Returns True if the update is an interrupt command.
    """

    return (
        not from_node
        and is_value_update(from_node, update_type, update_value)
        and "__interrupt__" in update_value
    )


def process_interrupt(update_value: list[Any], chat: AssistantChat | None = None):
    """
    Process an interrupt command.

    :param update: The update to process.
    :param chat: The chat associated with the interrupt, if any.
    """

    interrupt_message = update_value["__interrupt__"][0].value
    return interrupt_message


class Assistant:
    def __init__(self, chat: AssistantChat, new_message: HumanMessage | None = None):
        self._chat: AssistantChat = chat
        self._state: AssistantState | None = None
        self._context = AssistantExecutionContext.from_orm(chat=chat)
        self._graph_builder = AssistantGraphBuilder(context=self._context)
        self._graph: CompiledStateGraph | None = None
        self._config: RunnableConfig | None = None
        self._last_message: HumanMessage | None = new_message
        self._chunks = defaultdict(AIMessageChunk)

    def _get_config(self) -> RunnableConfig:
        if self._config is None:
            self._config = RunnableConfig(
                {
                    "configurable": {
                        "thread_id": self._chat.uuid,
                        "context": self._context,
                    }
                }
            )
        return self._config

    async def _get_graph(self):
        if self._graph is None:
            self._graph = await self._graph_builder.compile_full_graph()
        return self._graph

    @async_to_sync
    async def get_messages(self):
        """
        Fetch all messages from the state, saved by the checkpointer.
        """

        config = self._get_config()
        graph = await self._get_graph()
        snapshot = await graph.aget_state(config)
        messages = [
            msg for msg in snapshot.values["messages"] if msg.should_show_in_ui()
        ]
        if snapshot.interrupts:
            messages.append(snapshot.interrupts[-1])
        return messages

    def _process_custom_update(self, update: Any):
        return [update]

    async def _process_update(
        self, update: Any
    ) -> Optional[list[AssistantMessageUnion]]:
        """
        Process an update from the assistant graph. Considering the different stream
        modes, the update may contain different types of information. This function will
        handle different types of updates accordingly.

        :param update: The update to process.
        :return: A list of messages generated from the update to stream to the user, if
            any.
        """

        from_node, update_type, update_value = update
        if update_type == "custom":
            # Custom streams come from a tool call
            return self._process_custom_update(update_value)

        if is_interrupt(from_node, update_type, update_value):
            interrupt_message = process_interrupt(update_value)

            return [interrupt_message]

        if is_state_update(from_node, update_type, update_value):
            prev_state = self._state
            self._state = validate_state_update(update_value)
            if len(self._state.messages) > len(prev_state.messages):
                new_message = self._state.messages[-1]
                if new_message.should_show_in_ui():
                    return [new_message]
        elif is_message_update(from_node, update_type, update_value) and (
            new_message := self._process_message_update(update_value)
        ):
            return [new_message]
        return None

    def _process_message_update(self, update) -> Optional[AssistantMessageUnion]:
        """
        Process a message update from the assistant graph.

        :param update: The update to process.
        :return: The processed message, if any.
        """

        langchain_message, langchain_state = update
        if not isinstance(langchain_message, AIMessageChunk):
            return None

        node = langchain_state.get("langgraph_node")
        if not langchain_message.content:
            self._chunks[node] = langchain_message
            return None
        else:
            self._chunks[node] += langchain_message
            return get_message_by_node(node, content=self._chunks[node].content)

    async def astream(self) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Stream messages from the assistant.

        :param stream_messages: Whether to stream token messages as they are generated.
        :return: An async generator yielding messages.
        """

        stream_mode: list[StreamMode] = ["values", "updates", "messages", "custom"]

        config = self._get_config()
        self._graph = await self._get_graph()

        snapshot = await self._graph.aget_state(config)

        self._state = AssistantState(**snapshot.values)

        self._state.messages.append(self._last_message)
        if snapshot.interrupts:  # Resume from an interrupt
            next_input = Command(resume=self._last_message.content)
        else:  # New message
            next_input = self._state

        generator: AsyncIterator[Any] = self._graph.astream(
            next_input,
            config=config,
            stream_mode=stream_mode,
            subgraphs=True,
            durability="async",
        )

        try:
            async for update in generator:
                if messages := await self._process_update(update):
                    for message in messages:
                        yield message
        except GraphRecursionError:
            yield (
                AiErrorMessage(
                    code=AI_ERROR_MESSAGE_CODE.RECURSION_LIMIT_EXCEEDED,
                    content=(
                        "The assistant has reached the maximum number of steps. "
                        "You can explicitly ask to continue."
                    ),
                ),
            )
        except Exception:
            logger.exception("Error occurred while streaming updates")

            yield AiErrorMessage(
                code=AI_ERROR_MESSAGE_CODE.UNKNOWN,
                content="The assistant has encountered an error. Please try again.",
            )
