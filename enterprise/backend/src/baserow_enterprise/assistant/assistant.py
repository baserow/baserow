from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncGenerator, Callable, TypedDict

from django.conf import settings
from django.core.cache import cache
from django.utils import translation

import udspy
from udspy.callback import BaseCallback

from baserow.api.sessions import get_client_undo_redo_action_group_id
from baserow_enterprise.assistant.exceptions import (
    AssistantMessageCancelled,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.tools.navigation.types import AnyNavigationRequestType
from baserow_enterprise.assistant.tools.navigation.utils import unsafe_navigate_to
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
from .prompts import ASSISTANT_SYSTEM_PROMPT
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


class ChatSignature(udspy.Signature):
    __doc__ = f"{ASSISTANT_SYSTEM_PROMPT}\n TASK INSTRUCTIONS: \n"

    question: str = udspy.InputField()
    ui_context: dict[str, Any] | None = udspy.InputField(
        default=None,
        desc=(
            "The context the user is currently in. "
            "It contains information about the user, the workspace, open table, view, etc."
            "Whenever make sense, use it to ground your answer."
        ),
    )
    answer: str = udspy.OutputField()


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


class Assistant:
    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace

        self._init_lm_client()
        self._init_assistant()

    def _init_lm_client(self):
        lm_model = settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
        self._lm_client = udspy.LM(model=lm_model)

    def _init_assistant(self):
        self.tool_helpers = self.get_tool_helpers()
        tools = assistant_tool_registry.list_all_usable_tools(
            self._user, self._workspace, self.tool_helpers
        )
        self.callbacks = AssistantCallbacks(self.tool_helpers)
        self._assistant = udspy.ReAct(ChatSignature, tools=tools, max_iters=20)
        self.history = None

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

    async def aload_chat_history(self, limit=30):
        """
        Loads the chat history into a udspy.History object. It only loads complete
        message pairs (human + AI). The history will be in chronological order and must
        respect the module signature (question, answer).

        :param limit: The maximum number of message pairs to load.
        :return: None
        """

        last_saved_messages: list[AssistantChatMessage] = [
            msg async for msg in self._chat.messages.order_by("-created_on")[:limit]
        ]

        self.history = udspy.History()
        while len(last_saved_messages) >= 2:
            # Pop the oldest message pair to respect chronological order.
            first_message = last_saved_messages.pop()
            next_message = last_saved_messages[-1]
            if (
                first_message.role != AssistantChatMessage.Role.HUMAN
                or next_message.role != AssistantChatMessage.Role.AI
            ):
                continue

            self.history.add_user_message(first_message.content)
            ai_answer = last_saved_messages.pop()
            self.history.add_assistant_message(ai_answer.content)

    @lru_cache(maxsize=1)
    def check_llm_ready_or_raise(self):
        try:
            self._lm_client("Say ok if you can read this.")
        except Exception as e:
            raise AssistantModelNotSupportedError(
                f"The model '{self._lm_client.model}' is not supported or accessible: {e}"
            )

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

    async def _generate_chat_title(
        self, user_message: HumanMessage, ai_msg: AiMessage
    ) -> str:
        """
        Generates a title for the chat based on the user message and AI response.
        """

        title_generator = udspy.Predict(
            udspy.Signature.from_string(
                "user_message, ai_response -> chat_title",
                "Create a short title for the following chat conversation.",
            )
        )
        rsp = await title_generator.aforward(
            user_message=user_message.content,
            ai_response=ai_msg.content[:300],
        )
        return rsp.chat_title

    async def _acreate_ai_message_response(
        self,
        human_msg: HumanMessage,
        final_prediction: udspy.Prediction,
        sources: list[str],
    ) -> AiMessage:
        ai_msg = await self.acreate_chat_message(
            AssistantChatMessage.Role.AI,
            final_prediction.answer,
            artifacts={"sources": sources},
            action_group_id=get_client_undo_redo_action_group_id(self._user),
        )
        await AssistantChatPrediction.objects.acreate(
            human_message=human_msg,
            ai_response=ai_msg,
            prediction={
                "model": self._lm_client.model,
                "trajectory": final_prediction.trajectory,
                "reasoning": final_prediction.reasoning,
            },
        )

        # Yield final complete message
        return AiMessage(
            id=ai_msg.id,
            content=final_prediction.answer,
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

    async def _enhance_question_with_history(self, question: str) -> str:
        """Enhance the user question with chat history context if available."""

        if not self.history.messages:
            return question

        predictor = udspy.Predict("question, context -> enhanced_question")
        result = await predictor.aforward(
            question=question, context=self.history.messages
        )
        return result.enhanced_question

    async def _process_stream_event(
        self,
        event: Any,
        human_msg: AssistantChatMessage,
        human_message: HumanMessage,
        stream_reasoning: bool,
    ) -> tuple[list[AssistantMessageUnion], bool]:
        """
        Process a single event from the output stream.

        :param event: The event to process.
        :param human_msg: The human message instance.
        :param human_message: The human message data.
        :param stream_reasoning: Whether reasoning streaming is enabled.
        :return: a tuple of (messages_to_yield, updated_stream_reasoning_flag).
        """

        messages = []

        if isinstance(event, (AiThinkingMessage, AiNavigationMessage)):
            messages.append(event)
            return messages, True  # Enable reasoning streaming

        # Stream the final answer
        if isinstance(event, udspy.OutputStreamChunk):
            if event.field_name == "answer":
                messages.append(
                    AiMessageChunk(
                        content=event.content,
                        sources=self.callbacks.sources,
                    )
                )

        elif isinstance(event, udspy.Prediction):
            # sub-module predictions contain reasoning steps
            if "next_thought" in event and stream_reasoning:
                messages.append(AiReasoningChunk(content=event.next_thought))

            # final prediction contains the answer to the user question
            elif event.module is self._assistant:
                ai_msg = await self._acreate_ai_message_response(
                    human_msg, event, self.callbacks.sources
                )
                messages.append(ai_msg)

                # Generate chat title if needed
                if not self._chat.title:
                    chat_title = await self._generate_chat_title(human_message, ai_msg)
                    messages.append(ChatTitleMessage(content=chat_title))
                    self._chat.title = chat_title
                    await self._chat.asave(update_fields=["title", "updated_on"])

        return messages, stream_reasoning

    async def astream_messages(
        self, human_message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Streams the response to a user message.

        :param human_message: The message from the user.
        :return: An async generator that yields the response messages.
        """
        with udspy.settings.context(
            lm=self._lm_client,
            callbacks=[*udspy.settings.callbacks, self.callbacks],
        ):
            if self.history is None:
                await self.aload_chat_history()

            user_question = await self._enhance_question_with_history(
                human_message.content
            )

            output_stream = self._assistant.astream(
                question=user_question,
                ui_context=human_message.ui_context.model_dump_json(exclude_none=True),
            )

            human_msg = await self.acreate_chat_message(
                AssistantChatMessage.Role.HUMAN, human_message.content
            )

            cache_key = self._get_cancellation_cache_key()
            message_id = str(human_msg.id)
            yield AiStartedMessage(message_id=message_id)

            # Flag to wait for the first step in the reasoning to start streaming it
            stream_reasoning = False
            chunk_count = 0

            async for event in output_stream:
                # Periodically check for cancellation
                chunk_count += 1
                if chunk_count % 10 == 0:
                    self._check_cancellation(cache_key, message_id)

                messages, stream_reasoning = await self._process_stream_event(
                    event, human_msg, human_message, stream_reasoning
                )

                if messages:  # Don't return responses if cancelled
                    self._check_cancellation(cache_key, message_id)

                    for msg in messages:
                        yield msg
