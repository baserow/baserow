from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncGenerator, Callable, Tuple, TypedDict

from django.conf import settings
from django.core.cache import cache
from django.utils import translation
from django.utils.translation import gettext as _

import udspy
from udspy.callback import BaseCallback

from baserow.api.sessions import get_client_undo_redo_action_group_id
from baserow_enterprise.assistant.exceptions import (
    AssistantMessageCancelled,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.telemetry import PosthogTracingCallback
from baserow_enterprise.assistant.tools.navigation.types import AnyNavigationRequestType
from baserow_enterprise.assistant.tools.navigation.utils import unsafe_navigate_to
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
from .signatures import ChatSignature, RequestRouter
from .types import (
    AiMessage,
    AiMessageChunk,
    AiNavigationMessage,
    AiReasoningChunk,
    AiStartedMessage,
    AiThinkingMessage,
    AssistantMessageUnion,
    ChatTitleMessage,
    HumanMessage,
)


@dataclass
class ToolHelpers:
    update_status: Callable[[str], None]
    navigate_to: Callable[["AnyNavigationRequestType"], str]


class AssistantMessagePair(TypedDict):
    question: str
    answer: str


class AssistantCallbacks(BaseCallback):
    def __init__(self, tool_helpers: ToolHelpers | None = None):
        self.tool_helpers = tool_helpers
        self.tool_calls = {}
        self.sources = []

    def extend_sources(self, sources: list[str]) -> None:
        """
        Extends the current list of sources with new ones, avoiding duplicates.

        :param sources: The list of new source URLs to add.
        :return: None
        """

        self.sources.extend([s for s in sources if s not in self.sources])

    def on_tool_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """
        Called when a tool starts. It records the tool call and invokes the
        corresponding tool's on_tool_start method if it exists.

        :param call_id: The unique identifier of the tool call.
        :param instance: The instance of the tool being called.
        :param inputs: The inputs provided to the tool.
        """

        try:
            assistant_tool_registry.get(instance.name).on_tool_start(
                call_id, instance, inputs
            )
            self.tool_calls[call_id] = (instance, inputs)
        except assistant_tool_registry.does_not_exist_exception_class:
            pass

    def on_tool_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None,
    ) -> None:
        """
        Called when a tool ends. It invokes the corresponding tool's on_tool_end
        method if it exists and updates the sources if the tool produced any.

        :param call_id: The unique identifier of the tool call.
        :param outputs: The outputs returned by the tool, or None if there was an
            exception.
        :param exception: The exception raised by the tool, or None if it was
            successful.
        """

        if call_id not in self.tool_calls:
            return

        instance, inputs = self.tool_calls.pop(call_id)
        assistant_tool_registry.get(instance.name).on_tool_end(
            call_id, instance, inputs, outputs, exception
        )

        if exception is not None and self.tool_helpers is not None:
            self.tool_helpers.update_status(
                f"Calling the {instance.name} tool encountered an error."
            )

        # If the tool produced sources, add them to the overall list of sources.
        if isinstance(outputs, dict) and "sources" in outputs:
            self.extend_sources(outputs["sources"])


def get_assistant_cancellation_key(chat_uuid: str) -> str:
    """
    Get the Redis cache key for cancellation tracking.

    :param chat_uuid: The UUID of the assistant chat.
    :return: The cache key as a string.
    """

    return f"assistant:chat:{chat_uuid}:cancelled"


def set_assistant_cancellation_key(chat_uuid: str, timeout: int = 300) -> None:
    """
    Set the cancellation flag in the cache for the given chat UUID.

    :param chat_uuid: The UUID of the assistant chat.
    :param timeout: The time in seconds after which the cancellation flag expires.
    """

    cache_key = get_assistant_cancellation_key(chat_uuid)
    cache.set(cache_key, True, timeout=timeout)


def get_lm_client(
    model: str | None = None,
) -> "Assistant":
    """
    Returns a udspy.LM client configured with the specified model or the default model.

    :param model: The language model to use. If None, the default model from settings
        will be used.
    :return: A udspy.LM instance.
    """

    return udspy.LM(model=model or settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL)


@lru_cache(maxsize=1)
def check_lm_ready_or_raise() -> None:
    """
    Checks if the configured LLM is ready by making a test call. Raises
    AssistantModelNotSupportedError if the model is not supported or accessible.
    """

    lm = get_lm_client()
    try:
        lm("Respond in JSON: {'response': 'ok'}")
    except Exception as e:
        raise AssistantModelNotSupportedError(
            f"The model '{lm.model}' is not supported or accessible: {e}"
        )


class Assistant:
    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace

        self._lm_client = get_lm_client()
        self._init_assistant()

    def _init_assistant(self):
        self.history = None
        self.tool_helpers = self.get_tool_helpers()
        tools = [
            t if isinstance(t, udspy.Tool) else udspy.Tool(t)
            for t in assistant_tool_registry.list_all_usable_tools(
                self._user, self._workspace, self.tool_helpers
            )
        ]

        self._assistant_callbacks = AssistantCallbacks(self.tool_helpers)
        self._telemetry_callbacks = PosthogTracingCallback()
        self._callbacks = [self._assistant_callbacks, self._telemetry_callbacks]

        module_kwargs = {
            "temperature": settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE,
            "response_format": {"type": "json_object"},
        }
        self.search_user_docs_tool = self._get_search_user_docs_tool(tools)
        self.agent_tools = tools
        self._request_router = udspy.ChainOfThought(RequestRouter, **module_kwargs)
        self._assistant = udspy.ReAct(
            ChatSignature, tools=self.agent_tools, max_iters=20, **module_kwargs
        )

    def _get_search_user_docs_tool(
        self, tools: list[udspy.Tool | Callable]
    ) -> udspy.Tool | None:
        """
        Retrieves the search_user_docs tool from the list of tools if available.

        :param tools: The list of tools to search through.
        :return: The search_user_docs as udspy.Tool or None if not found.
        """

        search_user_docs_tool = next(
            (tool for tool in tools if tool.name == "search_user_docs"), None
        )
        if search_user_docs_tool is None or isinstance(
            search_user_docs_tool, udspy.Tool
        ):
            return search_user_docs_tool

        return udspy.Tool(search_user_docs_tool)

    async def acreate_chat_message(
        self,
        role: AssistantChatMessage.Role,
        content: str,
        artifacts: dict[str, Any] | None = None,
        **kwargs,
    ) -> AssistantChatMessage:
        """
        Creates and saves a new chat message.

        :param role: The role of the message (human or AI).
        :param content: The content of the message.
        :param artifacts: Optional artifacts associated with the message.
        :return: The created AssistantChatMessage instance.
        """

        message = AssistantChatMessage(
            chat=self._chat,
            role=role,
            content=content,
            **kwargs,
        )
        if artifacts:
            message.artifacts = artifacts

        await message.asave()
        return message

    def list_chat_messages(
        self, last_message_id: int | None = None, limit: int = 100
    ) -> list[AssistantChatMessage]:
        """
        Lists all chat messages in chronological order.

        :param last_message_id: The ID of the last message received. If provided, only
            messages before this ID will be returned.
        :param limit: The maximum number of messages to return.
        :return: A list of AssistantChatMessage instances.
        """

        queryset = (
            self._chat.messages.all()
            .select_related("prediction")
            .order_by("-created_on")
        )
        if last_message_id is not None:
            queryset = queryset.filter(id__lt=last_message_id)

        messages = []
        for msg in queryset[:limit]:
            if msg.role == AssistantChatMessage.Role.HUMAN:
                messages.append(
                    HumanMessage(
                        content=msg.content, id=msg.id, timestamp=msg.created_on
                    )
                )
            else:
                sentiment_data = {}
                if getattr(msg, "prediction", None):
                    sentiment_data = {
                        "can_submit_feedback": True,
                        "human_sentiment": msg.prediction.get_human_sentiment_display(),
                    }
                messages.append(
                    AiMessage(
                        content=msg.content,
                        id=msg.id,
                        timestamp=msg.created_on,
                        **sentiment_data,
                    )
                )
        return list(reversed(messages))

    async def afetch_chat_history(self, limit=30):
        """
        Loads the chat history into a udspy.History object. It only loads complete
        message pairs (human + AI). The history will be in chronological order and must
        respect the module signature (question, answer).

        :param limit: The maximum number of message pairs to load.
        :return: None
        """

        history = udspy.History()
        last_saved_messages: list[AssistantChatMessage] = [
            msg async for msg in self._chat.messages.order_by("-created_on")[:limit]
        ]

        while len(last_saved_messages) >= 2:
            # Pop the oldest message pair to respect chronological order.
            first_message = last_saved_messages.pop()
            next_message = last_saved_messages[-1]
            if (
                first_message.role != AssistantChatMessage.Role.HUMAN
                or next_message.role != AssistantChatMessage.Role.AI
            ):
                continue

            history.add_user_message(first_message.content)
            assistant_answer = last_saved_messages.pop()
            history.add_assistant_message(assistant_answer.content)

        return history

    def get_tool_helpers(self) -> ToolHelpers:
        def update_status_localized(status: str):
            """
            Sends a localized message to the frontend to update the assistant status.

            :param status: The status message to send.
            """

            with translation.override(self._user.profile.language):
                udspy.emit_event(AiThinkingMessage(content=status))

        return ToolHelpers(
            update_status=update_status_localized,
            navigate_to=unsafe_navigate_to,
        )

    async def _generate_chat_title(self, user_message: str) -> str:
        """
        Generates a title for the chat based on the user message and AI response.

        :param user_message: The latest user message in the chat.
        :return: The generated chat title.
        """

        title_generator = udspy.Predict(
            udspy.Signature.from_string(
                "user_message -> chat_title",
                "Create a short title for the following user request.",
            )
        )
        rsp = await title_generator.aforward(
            user_message=user_message,
        )
        return rsp.chat_title

    async def _acreate_ai_message_response(
        self,
        human_msg: HumanMessage,
        prediction: udspy.Prediction,
    ) -> AiMessage:
        """
        Creates and saves an AI chat message response based on the prediction. Stores
        the prediction in AssistantChatPrediction, linking it to the human message, so
        it can be referenced later to provide feedback.

        :param human_msg: The human message instance.
        :param prediction: The udspy.Prediction instance containing the AI response.
        :return: The created AiMessage instance to return to the user.
        """

        sources = self._assistant_callbacks.sources
        ai_msg = await self.acreate_chat_message(
            AssistantChatMessage.Role.AI,
            prediction.answer,
            artifacts={"sources": sources},
            action_group_id=get_client_undo_redo_action_group_id(self._user),
        )

        await AssistantChatPrediction.objects.acreate(
            human_message=human_msg,
            ai_response=ai_msg,
            prediction={k: v for k, v in prediction.items() if k != "module"},
        )

        # Yield final complete message
        return AiMessage(
            id=ai_msg.id,
            content=prediction.answer,
            sources=sources,
            can_submit_feedback=True,
        )

    def _get_cancellation_cache_key(self) -> str:
        """
        Get the Redis cache key for cancellation tracking.

        :return: The cache key as a string.
        """

        return get_assistant_cancellation_key(self._chat.uuid)

    def _check_cancellation(self, cache_key: str, message_id: str) -> None:
        """
        Check if the message generation has been cancelled.

        :param cache_key: The cache key to check for cancellation.
        :param message_id: The ID of the message being generated.
        :raises AssistantMessageCancelled: If the message generation has been cancelled.
        """

        if cache.get(cache_key):
            cache.delete(cache_key)
            raise AssistantMessageCancelled(message_id=message_id)

    async def get_router_stream(
        self, message: HumanMessage
    ) -> AsyncGenerator[Any, None]:
        """
        Returns an async generator that streams the router's response to a user

        :param message: The current user message that needs context from history.
        :return: An async generator that yields stream events.
        """

        self.history = await self.afetch_chat_history()

        return self._request_router.astream(
            question=message.content,
            conversation_history=RequestRouter.format_conversation_history(
                self.history
            ),
        )

    async def _process_router_stream(
        self,
        event: Any,
        human_msg: AssistantChatMessage,
    ) -> Tuple[list[AssistantMessageUnion], bool, udspy.Prediction | None]:
        """
        Process a single event from the smart router output stream.

        :param event: The event to process.
        :param human_msg: The human message instance.
        :return: a tuple of (messages_to_yield, prediction).
        """

        messages = []
        prediction = None

        if isinstance(event, (AiThinkingMessage, AiNavigationMessage)):
            messages.append(event)
            return messages, prediction

        # Stream the final answer
        if isinstance(event, udspy.OutputStreamChunk):
            if event.field_name == "answer" and event.content.strip():
                messages.append(
                    AiMessageChunk(
                        content=event.content,
                        sources=self._assistant_callbacks.sources,
                    )
                )

        elif isinstance(event, udspy.Prediction):
            if hasattr(event, "routing_decision"):
                prediction = event

            if getattr(event, "routing_decision", None) == "delegate_to_agent":
                messages.append(AiThinkingMessage(content=_("Thinking...")))
            elif getattr(event, "routing_decision", None) == "search_user_docs":
                if self.search_user_docs_tool is not None:
                    await self.search_user_docs_tool(question=event.search_query)
                else:
                    messages.append(
                        AiMessage(
                            content=_(
                                "I wanted to search the documentation for you, "
                                "but the search tool isn't currently available.\n\n"
                                "To enable documentation search, you'll need to set up "
                                "the local knowledge base. \n\n"
                                "You can find setup instructions at: https://baserow.io/user-docs"
                            ),
                        )
                    )
            elif getattr(event, "answer", None):
                ai_msg = await self._acreate_ai_message_response(human_msg, event)
                messages.append(ai_msg)

        return messages, prediction

    async def _process_agent_stream(
        self,
        event: Any,
        human_msg: AssistantChatMessage,
    ) -> Tuple[list[AssistantMessageUnion], udspy.Prediction | None]:
        """
        Process a single event from the output stream.

        :param event: The event to process.
        :param human_msg: The human message instance.
        :return: a tuple of (messages_to_yield, prediction).
        """

        messages = []
        prediction = None

        if isinstance(event, (AiThinkingMessage, AiNavigationMessage)):
            messages.append(event)
            return messages, prediction

        # Stream the final answer
        if isinstance(event, udspy.OutputStreamChunk):
            if (
                event.field_name == "answer"
                and event.module is self._assistant.extract_module
            ):
                messages.append(
                    AiMessageChunk(
                        content=event.content,
                        sources=self._assistant_callbacks.sources,
                    )
                )

        elif isinstance(event, udspy.Prediction):
            # final prediction contains the answer to the user question
            if event.module is self._assistant:
                prediction = event
                ai_msg = await self._acreate_ai_message_response(human_msg, prediction)
                messages.append(ai_msg)

            elif reasoning := getattr(event, "next_thought", None):
                messages.append(AiReasoningChunk(content=reasoning))

        return messages, prediction

    def get_agent_stream(
        self, message: HumanMessage, extracted_context: str
    ) -> AsyncGenerator[Any, None]:
        """
        Returns an async generator that streams the ReAct agent's response to a user
        message.

        :param user_message: The message from the user.
        :return: An async generator that yields stream events.
        """

        ui_context = message.ui_context.format() if message.ui_context else None

        return self._assistant.astream(
            question=message.content,
            context=extracted_context,
            ui_context=ui_context,
        )

    async def _process_stream(
        self,
        human_msg: HumanMessage,
        stream: AsyncGenerator[Any, None],
        process_event_func: Callable[
            [Any, AssistantChatMessage],
            Tuple[list[AssistantMessageUnion], udspy.Prediction | None],
        ],
    ) -> AsyncGenerator[Tuple[AssistantMessageUnion, udspy.Prediction | None], None]:
        chunk_count = 0
        cancellation_key = self._get_cancellation_cache_key()
        message_id = str(human_msg.id)

        async for event in stream:
            # Periodically check for cancellation
            chunk_count += 1
            if chunk_count % 10 == 0:
                self._check_cancellation(cancellation_key, message_id)

            messages, prediction = await process_event_func(event, human_msg)

            if messages:  # Don't return responses if cancelled
                self._check_cancellation(cancellation_key, message_id)

                for msg in messages:
                    yield msg, prediction

    async def astream_messages(
        self, message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Streams the response to a user message.

        :param human_message: The message from the user.
        :return: An async generator that yields the response messages.
        """

        human_msg = await self.acreate_chat_message(
            AssistantChatMessage.Role.HUMAN,
            message.content,
        )
        default_callbacks = udspy.settings.callbacks

        with udspy.settings.context(
            lm=self._lm_client,
            callbacks=[*default_callbacks, *self._callbacks],
        ), self._telemetry_callbacks.trace(self._chat, human_msg.content):
            message_id = str(human_msg.id)
            yield AiStartedMessage(message_id=message_id)

            router_stream = await self.get_router_stream(message)
            routing_decision, extracted_context = None, ""

            async for msg, prediction in self._process_stream(
                human_msg, router_stream, self._process_router_stream
            ):
                if prediction is not None:
                    routing_decision = prediction.routing_decision
                    extracted_context = prediction.extracted_context
                yield msg

            if routing_decision == "delegate_to_agent":
                agent_stream = self.get_agent_stream(
                    message,
                    extracted_context=extracted_context,
                )

                async for msg, __ in self._process_stream(
                    human_msg, agent_stream, self._process_agent_stream
                ):
                    yield msg

                # Generate chat title if needed
                if not self._chat.title:
                    chat_title = await self._generate_chat_title(human_msg.content)
                    self._chat.title = chat_title
                    await self._chat.asave(update_fields=["title", "updated_on"])
                    yield ChatTitleMessage(content=chat_title)
