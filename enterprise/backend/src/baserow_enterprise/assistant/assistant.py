from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncGenerator, Callable, TypedDict

from django.conf import settings
from django.utils import translation

from baserow.api.sessions import get_client_undo_redo_action_group_id
from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError
from baserow_enterprise.assistant.tools.navigation.types import AnyNavigationRequestType
from baserow_enterprise.assistant.tools.navigation.utils import unsafe_navigate_to
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .adapter import get_chat_adapter
from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
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


@dataclass
class ToolHelpers:
    update_status: Callable[[str], None]
    navigate_to: Callable[["AnyNavigationRequestType"], str]


class AssistantMessagePair(TypedDict):
    question: str
    answer: str


def get_assistant_callbacks():
    from dspy.utils.callback import BaseCallback

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

    return AssistantCallbacks()


def get_chat_signature():
    import dspy  # local import to save memory when not used

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

    return ChatSignature


class Assistant:
    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace

        self._init_lm_client()
        self._init_assistant()

    def _init_lm_client(self):
        import dspy  # local import to save memory when not used

        lm_model = settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL

        self._lm_client = dspy.LM(
            model=lm_model,
            cache=not settings.DEBUG,
            max_retries=5,
            max_tokens=32000,
        )

    def _init_assistant(self):
        from .react import ReAct  # local import to save memory when not used

        tool_helpers = self.get_tool_helpers()
        tools = assistant_tool_registry.list_all_usable_tools(
            self._user, self._workspace, tool_helpers
        )
        self._assistant = ReAct(get_chat_signature(), tools=tools)
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

    async def aload_chat_history(self, limit=20):
        """
        Loads the chat history into a dspy.History object. It only loads complete
        message pairs (human + AI). The history will be in chronological order and must
        respect the module signature (question, answer).

        :param limit: The maximum number of message pairs to load.
        :return: None
        """

        import dspy  # local import to save memory when not used

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

    @lru_cache(maxsize=1)
    def check_llm_ready_or_raise(self):
        import dspy  # local import to save memory when not used
        from litellm import get_supported_openai_params

        lm = self._lm_client
        params = get_supported_openai_params(lm.model)
        if params is None or "tools" not in params:
            raise AssistantModelNotSupportedError(
                f"The model '{lm.model}' is not supported or could not be found. "
                "Please make sure the model name is correct, it can use tools, "
                "and that your API key has access to it."
            )

        try:
            with dspy.context(lm=lm):
                lm("Say ok if you can read this.")
        except Exception as e:
            raise AssistantModelNotSupportedError(
                f"The model '{lm.model}' is not supported or accessible: {e}"
            )

    def get_tool_helpers(self) -> ToolHelpers:
        from dspy.dsp.utils.settings import settings as dspy_settings
        from dspy.streaming.messages import sync_send_to_stream

        def update_status_localized(status: str):
            """
            Sends a localized message to the frontend to update the assistant status.

            :param status: The status message to send.
            """

            with translation.override(self._user.profile.language):
                stream = dspy_settings.send_stream

                if stream is not None:
                    sync_send_to_stream(stream, AiThinkingMessage(content=status))

        return ToolHelpers(
            update_status=update_status_localized,
            navigate_to=unsafe_navigate_to,
        )

    async def astream_messages(
        self, human_message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Streams the response to a user message.

        :param human_message: The message from the user.
        :return: An async generator that yields the response messages.
        """

        import dspy  # local import to save memory when not used
        from dspy.primitives.prediction import Prediction
        from dspy.streaming import StreamListener, StreamResponse

        callback_manager = get_assistant_callbacks()

        with dspy.context(
            lm=self._lm_client,
            cache=not settings.DEBUG,
            callbacks=[*dspy.settings.config.callbacks, callback_manager],
            adapter=get_chat_adapter(),
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

            human_msg = await self.acreate_chat_message(
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
                elif isinstance(stream_chunk, (AiThinkingMessage, AiNavigationMessage)):
                    # forward thinking/navigation messages as-is to the frontend
                    yield stream_chunk
                elif isinstance(stream_chunk, Prediction):
                    # At the end of the prediction, save the AI message and the
                    # prediction details for future analysis and feedback.
                    ai_msg = await self.acreate_chat_message(
                        AssistantChatMessage.Role.AI,
                        answer,
                        artifacts={"sources": callback_manager.sources},
                        action_group_id=get_client_undo_redo_action_group_id(
                            self._user
                        ),
                    )
                    await AssistantChatPrediction.objects.acreate(
                        human_message=human_msg,
                        ai_response=ai_msg,
                        prediction={
                            "model": self._lm_client.model,
                            "trajectory": stream_chunk.trajectory,
                            "reasoning": stream_chunk.reasoning,
                        },
                    )
                    # In case the streaming didn't work, make sure we yield at least one
                    # final message with the complete answer.
                    yield AiMessage(
                        id=ai_msg.id,
                        content=stream_chunk.answer,
                        sources=callback_manager.sources,
                        can_submit_feedback=True,
                    )

            if not self._chat.title:
                title_generator = dspy.Predict("question -> chat_title")
                rsp = await title_generator.acall(question=human_message.content)
                self._chat.title = rsp.chat_title
                yield ChatTitleMessage(content=self._chat.title)
                await self._chat.asave(update_fields=["title", "updated_on"])
