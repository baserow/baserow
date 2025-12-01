from enum import StrEnum

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance
from rest_framework import serializers

from baserow_enterprise.assistant.models import AssistantChat, AssistantChatPrediction
from baserow_enterprise.assistant.types import (
    AssistantMessageType,
    AssistantMessageUnion,
)


class AssistantChatsRequestSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    offset = serializers.IntegerField(default=0, min_value=0)
    limit = serializers.IntegerField(default=100, max_value=100, min_value=1)


class UIContextApplicationSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The unique ID of the application.")
    name = serializers.CharField(help_text="The name of the application.")


class UIContextTableSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ID of the table.")
    name = serializers.CharField(help_text="The name of the table.")


class UIContextViewSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ID of the view.")
    name = serializers.CharField(help_text="The name of the view.")
    type = serializers.CharField(help_text="The type of the view.")


class UIContextWorkspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ID of the workspace.")
    name = serializers.CharField(help_text="The name of the workspace.")


class UIContextPageSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The unique ID of the page.")
    name = serializers.CharField(help_text="The name of the page.")


class UIContextWorkflowSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The unique ID of the workflow.")
    name = serializers.CharField(help_text="The name of the workflow.")


class UIContextSerializer(serializers.Serializer):
    workspace = UIContextWorkspaceSerializer()
    # database builder context
    database = UIContextApplicationSerializer(
        required=False,
        help_text="The application the user is currently in, e.g. 'database'.",
    )
    table = UIContextTableSerializer(
        required=False,
        help_text="The table the user is currently viewing, if any.",
    )
    view = UIContextViewSerializer(
        required=False,
        help_text="The view the user is currently viewing, if any.",
    )
    # application builder context
    application = UIContextApplicationSerializer(
        required=False,
        help_text="The application the user is currently in, e.g. 'application'.",
    )
    page = UIContextPageSerializer(
        required=False,
        help_text="The page the user is currently viewing, if any.",
    )
    # automation builder context
    automation = UIContextApplicationSerializer(
        required=False,
        help_text="The application the user is currently in, e.g. 'automation'.",
    )
    workflow = UIContextWorkflowSerializer(
        required=False,
        help_text="The workflow the user is currently viewing, if any.",
    )
    # dashboard builder context
    dashboard = UIContextApplicationSerializer(
        required=False,
        help_text="The application the user is currently in, e.g. 'dashboard'.",
    )
    # user context
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


class AiMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        help_text="The unique ID of the message.", required=False
    )
    type = serializers.CharField(default=AssistantMessageType.AI_MESSAGE)
    content = serializers.CharField(help_text="The content of the AI message.")
    timestamp = serializers.DateTimeField(
        required=False, help_text="The timestamp of the message."
    )
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text=(
            "The list of relevant source URLs referenced in the knowledge. Can be empty or null."
        ),
    )
    can_submit_feedback = serializers.BooleanField(
        default=False,
        help_text=(
            "Whether the user can submit feedback for this message. "
            "Only true for messages with an associated prediction."
        ),
    )
    human_sentiment = serializers.ChoiceField(
        required=False,
        allow_null=True,
        choices=["LIKE", "DISLIKE"],
        help_text="The sentiment for the message, if it has been rated.",
    )


class AiThinkingSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_THINKING)
    content = serializers.CharField(
        default="The AI is thinking...",
        help_text=("The message to show while the AI is thinking"),
    )


class AiReasoningSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_REASONING)
    content = serializers.CharField(
        help_text="The reasoning content of the AI message."
    )


class AiNavigationSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_NAVIGATION)
    location = serializers.DictField(help_text=("The location to navigate to."))


class AiErrorMessageSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_ERROR)
    code = serializers.CharField(
        help_text="A short error code that can be used to identify the error."
    )
    content = serializers.CharField(help_text="The error message content.")


class ChatTitleMessageSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.CHAT_TITLE)
    content = serializers.CharField(help_text="The chat title message content.")


class AiStartedSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_STARTED)
    message_id = serializers.CharField(
        help_text="The ID of the message being generated."
    )


class AiCancelledSerializer(serializers.Serializer):
    type = serializers.CharField(default=AssistantMessageType.AI_CANCELLED)
    message_id = serializers.CharField(
        help_text="The ID of the message that was cancelled."
    )


class HumanMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The unique ID of the message.")
    type = serializers.CharField(default=AssistantMessageType.HUMAN)
    content = serializers.CharField(help_text="The content of the human message.")
    timestamp = serializers.DateTimeField(
        required=False, help_text="The timestamp of the message."
    )


TYPE_SERIALIZER_MAP = {
    AssistantMessageType.CHAT_TITLE: ChatTitleMessageSerializer,
    AssistantMessageType.HUMAN: HumanMessageSerializer,
    AssistantMessageType.AI_MESSAGE: AiMessageSerializer,
    AssistantMessageType.AI_THINKING: AiThinkingSerializer,  # Update the satus bar in the UI
    AssistantMessageType.AI_REASONING: AiReasoningSerializer,  # Show reasoning steps before the final answer
    AssistantMessageType.AI_NAVIGATION: AiNavigationSerializer,
    AssistantMessageType.AI_ERROR: AiErrorMessageSerializer,
    AssistantMessageType.AI_STARTED: AiStartedSerializer,
    AssistantMessageType.AI_CANCELLED: AiCancelledSerializer,
}


class AssistantMessageSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[(msg_type, msg_type) for msg_type in TYPE_SERIALIZER_MAP.keys()],
        required=False,
        help_text=(
            "The type of the message content. Used to distinguish how the content "
            "of the message is used in the frontend."
        ),
    )

    def to_representation(self, instance):
        # Handle both dict and object instances
        if isinstance(instance, dict):
            msg_type = instance.get("type")
            data = instance
        else:
            msg_type = getattr(instance, "type", None)
            # Convert Pydantic model to dict if needed
            if hasattr(instance, "model_dump"):
                data = instance.model_dump()
            else:
                data = instance

        # Get the appropriate serializer for this message type
        serializer_class = TYPE_SERIALIZER_MAP.get(msg_type)
        if serializer_class:
            # Use the type-specific serializer to represent the data
            return serializer_class(data).data

        # Fallback for unknown types
        return {"type": msg_type}

    @classmethod
    def can_serialize(cls, message: AssistantMessageUnion) -> bool:
        return message.type in TYPE_SERIALIZER_MAP

    @classmethod
    def from_assistant_message(
        cls, message: AssistantMessageUnion
    ) -> "AssistantMessageSerializer":
        if message.type not in TYPE_SERIALIZER_MAP:
            raise ValueError(
                f"Unknown message type {message.type}. Cannot serialize. "
                "Did you forget to add it to TYPE_SERIALIZER_MAP?"
            )

        serializer = cls(data=message.model_dump())
        serializer.is_valid(raise_exception=True)
        return serializer


class AssistantChatMessagesSerializer(serializers.Serializer):
    messages = AssistantMessageSerializer(many=True)

    def to_representation(self, instance):
        """Convert the instance to the proper representation."""

        if isinstance(instance, dict) and "messages" in instance:
            messages = instance["messages"]
        else:
            messages = getattr(instance, "messages", [])

        # Filter out messages that can't be serialized
        serializable_messages = [
            msg
            for msg in messages
            if hasattr(msg, "type") and AssistantMessageSerializer.can_serialize(msg)
        ]

        return {
            "messages": AssistantMessageSerializer(
                serializable_messages, many=True
            ).data
        }


# Custom extension to make drf-spectacular use the polymorphic serializer
class AssistantMessageSerializerExtension(OpenApiSerializerExtension):
    target_class = (
        "baserow_enterprise.api.assistant.serializers.AssistantMessageSerializer"
    )

    def map_serializer(self, auto_schema, direction):
        return self._map_serializer(auto_schema, direction, TYPE_SERIALIZER_MAP)

    def _map_serializer(self, auto_schema, direction, mapping):
        sub_components = []

        for key, serializer_class in mapping.items():
            sub_serializer = force_instance(serializer_class)
            resolved = auto_schema.resolve_serializer(sub_serializer, direction)
            schema = resolved.ref

            if isinstance(schema, list):
                for item in schema:
                    sub_components.append((key, item))
            else:
                sub_components.append((key, schema))

        return {
            "oneOf": [schema for _, schema in sub_components],
            "discriminator": {
                "propertyName": "type",
                "mapping": {
                    key: value["$ref"]
                    for key, value in sub_components
                    if isinstance(value, dict) and "$ref" in value
                },
            },
        }


class AssistantRateChatMessageSerializer(serializers.Serializer):
    sentiment = serializers.ChoiceField(
        required=True,
        allow_null=True,
        choices=["LIKE", "DISLIKE"],
        help_text="The sentiment for the message.",
    )
    feedback = serializers.CharField(
        help_text="Optional feedback about the message.",
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def to_internal_value(self, data):
        validated_data = super().to_internal_value(data)
        validated_data["sentiment"] = AssistantChatPrediction.SENTIMENT_MAP.get(
            data.get("sentiment")
        )
        # Additional feedback is only allowed for DISLIKE sentiment
        if data["sentiment"] != "DISLIKE":
            validated_data["feedback"] = ""
        return validated_data
