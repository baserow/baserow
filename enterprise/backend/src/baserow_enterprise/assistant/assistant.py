from collections import defaultdict
from typing import Any, AsyncGenerator, AsyncIterator, Optional

from asgiref.sync import async_to_sync
from langchain_core.messages import AIMessageChunk
from langchain_core.runnables.config import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.types import StreamMode
from loguru import logger

from .graph.base import AssistantGraph, Node
from .models import AssistantChat
from .types import (
    AiErrorMessage,
    AiErrorMessageCode,
    AiMessage,
    AssistantMessageUnion,
    AssistantState,
    ChatTitleMessage,
    HumanMessage,
)


def is_state_update(update: list[Any]):
    """
    Returns True if the update is an update of the assistant graph state.
    """

    return len(update) == 2 and update[0] == "values"


def is_message_update(update: list[Any]):
    """
    Returns True if the update comes from a streaming update. This happens when the
    model defines streaming=True, so that every token is streamed as it is generated.
    """

    return len(update) == 2 and update[0] == "messages"


def validate_state_update(state_update: dict[Any, Any]) -> AssistantState:
    """
    Validate the state update against the AssistantState model.
    """

    return AssistantState.model_validate(state_update)


def get_message_by_node(node: Node, **kwargs) -> AssistantMessageUnion | None:
    """
    Returns the message associated with a specific node in the assistant graph.

    :param node: The node to get the message for.
    :param kwargs: Additional keyword arguments to pass to the message constructor.
    :return: The message associated with the specified node, or None if the node is not
        recognized.
    """

    if node == Node.ROOT:
        return AiMessage(**kwargs)
    elif node == Node.TITLE_GENERATOR:
        return ChatTitleMessage(**kwargs)


class Assistant:
    def __init__(self, chat: AssistantChat, new_message: HumanMessage | None = None):
        self.chat = chat
        self.user = chat.user
        self.workspace = chat.workspace
        self._state = None
        self._graph_builder = AssistantGraph(self.chat)
        self._graph = None
        self._last_message = new_message
        self._chunks = defaultdict(AIMessageChunk)

    def _get_config(self) -> RunnableConfig:
        return {
            "configurable": {
                "thread_id": self.chat.uuid,
                "chat": self.chat,
                "user": self.user,
                "workspace": self.workspace,
            }
        }

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
        return snapshot.values["messages"]

    def _init_state(self) -> AssistantState:
        """
        Initialize the assistant state.
        """

        messages = []
        if self._last_message:
            messages.append(self._last_message)
        return AssistantState(messages=messages)

    def _process_update(self, update: Any) -> Optional[list[AssistantMessageUnion]]:
        """
        Process an update from the assistant graph. Considering the different stream
        modes, the update may contain different types of information. This function will
        handle different types of updates accordingly.

        :param update: The update to process.
        :return: A list of messages generated from the update to stream to the user, if
            any.
        """

        # remove the first element, which is the node/subgraph node name
        update = update[1:]
        if is_state_update(update):
            _, new_state = update
            self._state = validate_state_update(new_state)
        elif is_message_update(update) and (
            new_message := self._process_message_update(update)
        ):
            return [new_message]
        return None

    def _process_message_update(self, update) -> Optional[AssistantMessageUnion]:
        """
        Process a message update from the assistant graph.

        :param update: The update to process.
        :return: The processed message, if any.
        """

        langchain_message, langchain_state = update[1]
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

        self._state = self._init_state()
        config = self._get_config()

        stream_mode: list[StreamMode] = ["values", "updates", "messages"]

        graph = await self._get_graph()
        generator: AsyncIterator[Any] = graph.astream(
            self._state, config=config, stream_mode=stream_mode, subgraphs=True
        )

        try:
            async for update in generator:
                if messages := self._process_update(update):
                    for message in messages:
                        yield message
        except GraphRecursionError:
            yield (
                AiErrorMessage(
                    code=AiErrorMessageCode.RECURSION_LIMIT_EXCEEDED,
                    content=(
                        "The assistant has reached the maximum number of steps. "
                        "You can explicitly ask to continue."
                    ),
                ),
            )
        except Exception:
            logger.exception("Error occurred while streaming updates")

            yield AiErrorMessage(
                code=AiErrorMessageCode.UNKNOWN,
                content="The assistant has encountered an error. Please try again.",
            )
