from rest_framework import serializers

from baserow_enterprise.assistant.graph.base import StrEnum
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.types import BaseMessage, HumanMessage


class AssistantChatsRequestSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    offset = serializers.IntegerField(default=0, min_value=0)
    limit = serializers.IntegerField(default=100, max_value=100, min_value=1)


class UIContextWorkspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ID of the workspace.")
    name = serializers.CharField(help_text="The name of the workspace.")


class UIContextSerializer(serializers.Serializer):
    workspace = UIContextWorkspaceSerializer()
    timezone = serializers.CharField(
        required=False,
        help_text="The timezone of the user, e.g. 'Europe/Amsterdam'.",
        default="UTC",
    )


class AssistantMessageRequestSerializer(serializers.Serializer):
    content = serializers.CharField(help_text="The content of the message.")
    ui_context = UIContextSerializer(
        help_text=(
            "The UI context related to what the user was looking at when the message was sent."
        )
    )


class AssistantChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantChat
        fields = (
            "uuid",
            "user_id",
            "workspace_id",
            "title",
            "status",
            "created_on",
            "updated_on",
        )


class AssistantMessageRole(StrEnum):
    HUMAN = "human"
    AI = "ai"


class AssistantMessageType(StrEnum):
    MESSAGE = "ai/message"
    """
    The chat message itself (default)
    """
    ERROR = "ai/error"
    """
    Use to signal that the AI has failed to process the message
    """
    CHAT_TITLE = "chat/title"
    """
    Use to signal the chat title should be updated with the message content
    """


class AssistantMessageSerializer(serializers.Serializer):
    id = serializers.UUIDField(help_text="The unique UUID of the message.")
    content = serializers.CharField(help_text="The content of the message.", default="")
    role = serializers.ChoiceField(
        choices=[
            (AssistantMessageRole.HUMAN, "Human"),
            (AssistantMessageRole.AI, "AI"),
        ],
        default=AssistantMessageRole.AI,
        help_text="The role of the message sender.",
    )
    type = serializers.ChoiceField(
        choices=[
            (AssistantMessageType.MESSAGE, "Message"),
            (AssistantMessageType.ERROR, "Error"),
            (AssistantMessageType.CHAT_TITLE, "Chat Title"),
        ],
        required=False,
        help_text=(
            "The type of the message content. Used to distinguish how the content "
            "of the message is used in the frontend."
        ),
    )

    @classmethod
    def from_assistant_message(cls, message: BaseMessage):
        data = {
            "id": message.id,
            "content": message.content,
        }
        if isinstance(message, HumanMessage):
            data["role"] = AssistantMessageRole.HUMAN
        else:
            data["role"] = AssistantMessageRole.AI
            data["type"] = message.type

        serializer = cls(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer


class AssistantChatMessageSerializer(serializers.Serializer):
    messages = AssistantMessageSerializer(many=True)
