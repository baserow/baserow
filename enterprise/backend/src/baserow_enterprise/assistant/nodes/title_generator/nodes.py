from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.nodes.base import AssistantNode
from baserow_enterprise.assistant.types import (
    AssistantState,
    HumanMessage,
    PartialAssistantState,
)
from baserow_enterprise.assistant.utils.helpers import find_last_message_of_type

from .prompts import TITLE_GENERATION_PROMPT


class TitleGeneratorNode(AssistantNode):
    def run(
        self, state: AssistantState, config: RunnableConfig
    ) -> PartialAssistantState | None:
        already_has_title = bool(self.chat.title.strip())
        if already_has_title:
            return None

        last_human_message = find_last_message_of_type(state.messages, HumanMessage)
        if not last_human_message:
            return None

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

        title = runnable.invoke(
            {"user_input": last_human_message.content}, config=config
        )
        self.chat.title = title[: AssistantChat.TITLE_MAX_LENGTH].strip().capitalize()
        self.chat.save()

        return None

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-4.1-nano",
            temperature=0.7,
            max_completion_tokens=100,
        )
