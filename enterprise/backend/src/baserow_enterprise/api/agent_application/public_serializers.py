"""
Serializers of the public web chat endpoints. They are the only way
conversation data reaches an anonymous visitor over HTTP, so they expose
exactly what the exposure contract in `agent_application/channels/web.py`
allows: the visitor's own messages, the agent's final answers and a coarse
status. Realtime events are filtered by `realtime.public_chat_event`.
"""

from rest_framework import serializers

from baserow_enterprise.agent_application.channels.web import (
    PUBLIC_STATUS,
    public_chat_status,
)
from baserow_enterprise.agent_application.models import AgentChatMessage


class PublicAgentChatInfoSerializer(serializers.Serializer):
    title = serializers.CharField()
    welcome_text = serializers.CharField(allow_blank=True)
    agent_name = serializers.CharField()
    has_password = serializers.BooleanField()


class PublicAgentChatAuthRequestSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=128, allow_blank=True)


class PublicAgentChatAuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()


class PublicAgentChatSendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=8000, trim_whitespace=True)


class PublicAgentChatMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=("human", "ai"))
    content = serializers.CharField()
    created_on = serializers.DateTimeField()


class PublicAgentChatConversationSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=sorted(set(PUBLIC_STATUS.values())),
        help_text="A coarse status: the visitor never sees why a run paused.",
    )
    messages = PublicAgentChatMessageSerializer(many=True)


class PublicAgentChatMessageSentSerializer(serializers.Serializer):
    message_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=("working",))


def serialize_public_message(message: AgentChatMessage) -> dict | None:
    """
    A visitor sees human messages and the text of finished AI answers; system
    messages, attachments, artifacts (reasoning, tool calls, approvals) and
    empty or cancelled answers are left out.
    """

    if message.role == AgentChatMessage.Role.HUMAN:
        role = "human"
    elif message.role == AgentChatMessage.Role.AI and message.content:
        role = "ai"
    else:
        return None
    return {
        "id": message.id,
        "role": role,
        "content": message.content,
        "created_on": message.created_on,
    }


def serialize_public_conversation(chat, messages) -> dict:
    return PublicAgentChatConversationSerializer(
        {
            "uuid": chat.uuid,
            "status": public_chat_status(chat.status),
            "messages": [
                data
                for data in (serialize_public_message(message) for message in messages)
                if data is not None
            ],
        }
    ).data
