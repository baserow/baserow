from datetime import datetime
from zoneinfo import ZoneInfo

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig

from baserow_enterprise.assistant.nodes.base import AssistantNode
from baserow_enterprise.assistant.nodes.root.prompts import ROOT_SYSTEM_PROMPT
from baserow_enterprise.assistant.types import (
    AssistantState,
    PartialAssistantState,
    ToolCall,
)
from baserow_enterprise.assistant.utils.helpers import AiMessage, get_buffer_string


class RootNode(AssistantNode):
    def run(self, state: AssistantState, config: RunnableConfig):
        ui_context = self._get_ui_context(state)
        timezone = ui_context.timezone if ui_context else "UTC"
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", ROOT_SYSTEM_PROMPT),
            ],
            template_format="mustache",
        )
        chain = prompt | self._model
        message = chain.invoke(
            {
                "user_id": self.user.id,
                "user_name": self.user.first_name,
                "user_email": self.user.email,
                "current_date": datetime.now(tz=ZoneInfo(timezone)).isoformat(),
                "timezone": timezone,
                "messages": get_buffer_string(state.messages),
                "ui_context": ui_context,
            },
            config=config,
        )

        return PartialAssistantState(
            messages=[
                AiMessage(
                    content=str(message.content),
                    tool_calls=[
                        ToolCall(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["args"],
                        )
                        for tool_call in message.tool_calls
                    ],
                ),
            ],
        )

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-4.1",
            temperature=0.3,
            streaming=True,
            stream_usage=True,
        )
