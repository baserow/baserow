from rest_framework import serializers

from baserow.api.chat_runs.serializers import ChatRunStreamQuerySerializer
from baserow.contrib.agent.models import AgentMessage


class PublicChatInfoSerializer(serializers.Serializer):
    title = serializers.CharField(
        help_text="The chat's title, or the agent's name. Empty for a password "
        "protected chat until the request carries a valid token."
    )
    welcome_text = serializers.CharField(
        help_text="Shown before the first message. Empty for a password protected "
        "chat until the request carries a valid token."
    )
    password_protected = serializers.BooleanField()


class PublicChatAuthRequestSerializer(serializers.Serializer):
    password = serializers.CharField()


class PublicChatAuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(
        help_text="Send it in the `Baserow-Agent-Chat-Authorization` header as "
        "`JWT <token>` to start a conversation."
    )


class PublicChatMessageSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid")

    class Meta:
        model = AgentMessage
        fields = ("id", "role", "content", "status", "created_on")


class PublicChatConversationSerializer(serializers.Serializer):
    messages = PublicChatMessageSerializer(many=True)
    run_id = serializers.UUIDField(
        allow_null=True, help_text="The run writing a reply now, or null."
    )


class PublicChatConversationStartedSerializer(PublicChatConversationSerializer):
    token = serializers.CharField(
        help_text="Send it in the `Baserow-Agent-Chat-Authorization` header as "
        "`JWT <token>` to continue the conversation."
    )


class PublicChatStopSerializer(serializers.Serializer):
    status = serializers.CharField(
        allow_null=True,
        help_text="The status of the run after the stop request, or null when the "
        "agent wasn't replying.",
    )


class PublicChatStreamQuerySerializer(ChatRunStreamQuerySerializer):
    run_id = serializers.UUIDField(help_text="The run writing the reply to follow.")
