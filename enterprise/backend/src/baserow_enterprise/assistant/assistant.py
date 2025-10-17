from typing import Any, AsyncGenerator, TypedDict

from django.conf import settings

import dspy
from dspy.primitives.prediction import Prediction
from dspy.streaming import StreamListener, StreamResponse
from dspy.utils.callback import BaseCallback

from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .adapter import ChatAdapter
from .models import AssistantChat, AssistantChatMessage
from .react import ReAct
from .types import (
    AiMessage,
    AiMessageChunk,
    AiNavigationMessage,
    AiThinkingMessage,
    AssistantMessageUnion,
    ChatTitleMessage,
    HumanMessage,
    UIContext,
)
from .utils import ensure_llm_model_accessible


class ChatSignature(dspy.Signature):
    question: str = dspy.InputField()
    history: dspy.History = dspy.InputField()
    ui_context: UIContext | None = dspy.InputField(
        default=None,
        desc=(
            "The frontend UI content the user is currently in. "
            "Whenever make sense, use it to ground your answer."
        ),
    )
    answer: str = dspy.OutputField()


class AssistantMessagePair(TypedDict):
    question: str
    answer: str


class AssistantCallbacks(BaseCallback):
    def __init__(self):
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

        # If the tool produced sources, add them to the overall list of sources.
        if isinstance(outputs, dict) and "sources" in outputs:
            self.extend_sources(outputs["sources"])


class Assistant:
    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace

        lm_model = settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
        self._lm_client = dspy.LM(
            model=lm_model,
            cache=not settings.DEBUG,
            max_retries=5,
        )

        tools = assistant_tool_registry.list_all_usable_tools(
            self._user, self._workspace
        )
        self._assistant = ReAct(ChatSignature, tools=tools)
        self.history = None

    async def acreate_chat_message(
        self,
        role: AssistantChatMessage.Role,
        content: str,
        artifacts: dict[str, Any] | None = None,
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
        )
        if artifacts:
            message.artifacts = artifacts
        return await message.asave()

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

        queryset = self._chat.messages.all().order_by("-created_on")
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
                messages.append(
                    AiMessage(content=msg.content, id=msg.id, timestamp=msg.created_on)
                )
        return list(reversed(messages))

    async def aload_chat_history(self, limit=20):
        """
        Loads the chat history into a dspy.History object. It only loads complete
        message pairs (human + AI). The history will be in chronological order and must
        respect the module signature (question, answer).

        :param limit: The maximum number of message pairs to load.
        :return: None
        """

        last_saved_messages: list[AssistantChatMessage] = [
            msg async for msg in self._chat.messages.order_by("-created_on")[:limit]
        ]

        messages = []
        while len(last_saved_messages) >= 2:
            first_message = last_saved_messages.pop()
            next_message = last_saved_messages[-1]
            if (
                first_message.role != AssistantChatMessage.Role.HUMAN
                or next_message.role != AssistantChatMessage.Role.AI
            ):
                continue

            human_question = first_message
            ai_answer = last_saved_messages.pop()
            messages.append(
                AssistantMessagePair(
                    question=human_question.content,
                    answer=ai_answer.content,
                )
            )

        self.history = dspy.History(messages=messages)

    async def astream_messages(
        self, human_message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Streams the response to a user message.

        :param human_message: The message from the user.
        :return: An async generator that yields the response messages.
        """

        # The first time, make sure the model and api_key are setup correctly
        ensure_llm_model_accessible(self._lm_client)

        callback_manager = AssistantCallbacks()

        with dspy.context(
            lm=self._lm_client,
            cache=not settings.DEBUG,
            callbacks=[*dspy.settings.config.callbacks, callback_manager],
            adapter=ChatAdapter(),
        ):
            if self.history is None:
                await self.aload_chat_history()

            # Follow the stream of all output fields
            stream_listeners = [
                StreamListener(signature_field_name="answer"),
            ]

            stream_predict = dspy.streamify(
                self._assistant,
                stream_listeners=stream_listeners,
            )
            output_stream = stream_predict(
                history=self.history,
                question=human_message.content,
                ui_context=human_message.ui_context.model_dump_json(
                    exclude_none=True, indent=2
                ),
            )

            await self.acreate_chat_message(
                AssistantChatMessage.Role.HUMAN, human_message.content
            )

            answer = ""
            async for stream_chunk in output_stream:
                if isinstance(stream_chunk, StreamResponse):
                    # Accumulate chunks per field to deliver full, real‐time updates.
                    if stream_chunk.signature_field_name == "answer":
                        answer += stream_chunk.chunk
                        yield AiMessageChunk(
                            content=answer, sources=callback_manager.sources
                        )
                elif isinstance(stream_chunk, Prediction):
                    yield AiMessageChunk(
                        content=stream_chunk.answer, sources=callback_manager.sources
                    )
                    await self.acreate_chat_message(
                        AssistantChatMessage.Role.AI,
                        answer,
                        artifacts={"sources": callback_manager.sources},
                    )

                elif isinstance(stream_chunk, (AiThinkingMessage, AiNavigationMessage)):
                    # forward thinking/navigation messages as-is to the frontend
                    yield stream_chunk

            if not self._chat.title:
                title_generator = dspy.Predict("question -> chat_title")
                rsp = await title_generator.acall(question=human_message.content)
                self._chat.title = rsp.chat_title
                yield ChatTitleMessage(content=self._chat.title)
                await self._chat.asave(update_fields=["title", "updated_on"])
