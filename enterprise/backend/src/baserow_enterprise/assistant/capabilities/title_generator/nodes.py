from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from baserow_enterprise.assistant.capabilities.base import AssistantNode
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.types import (
    AssistantState,
    HumanMessage,
    PartialAssistantState,
)
from baserow_enterprise.assistant.utils.helpers import find_last_message_of_type

from .prompts import TITLE_GENERATION_PROMPT


class TitleGeneratorNode(AssistantNode):
    def _generate_chat_title(
        self, last_human_message: HumanMessage, config: RunnableConfig
    ) -> str:
        runnable = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", TITLE_GENERATION_PROMPT),
                    ("user", "{user_input}"),
                ]
            )
            | self._model
            | StrOutputParser()
        )

        generated_title = runnable.invoke(
            {"user_input": last_human_message.content}, config=config
        )
        return generated_title[: AssistantChat.TITLE_MAX_LENGTH].strip().capitalize()

    def run(
        self, state: AssistantState, config: RunnableConfig
    ) -> PartialAssistantState | None:
        """
        If the chat does not already have a title, generate a title based on the last user
        message and update the chat model instance.

        :param state: The current state of the assistant.
        :param config: The runnable config containing user and workspace information.
        :return: None
        """

        current_chat = self._context.chat
        already_has_title = bool(current_chat.title.strip())
        if already_has_title:
            return None

        last_human_message = find_last_message_of_type(state.messages, HumanMessage)
        if not last_human_message:
            return None

        new_title = self._generate_chat_title(last_human_message, config)
        if new_title:
            current_chat.title = new_title
            AssistantChat.objects.filter(id=current_chat.id).update(title=new_title)

        return None

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-4.1-nano",
            temperature=0.7,
            max_completion_tokens=100,
        )
