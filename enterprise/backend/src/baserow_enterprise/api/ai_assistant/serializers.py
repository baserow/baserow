from rest_framework import serializers
from baserow_enterprise.ai_assistant.models import AssistantChat


class AssistantChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantChat
        fields = ["uid", "title", "status", "created_on", "updated_on"]
        read_only_fields = ["uid", "created_on", "updated_on"]


class DatabaseContextSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["database"], default="database")
    database_id = serializers.IntegerField()
    table_id = serializers.IntegerField()
    view_id = serializers.IntegerField(required=False)
    field_id = serializers.IntegerField(required=False)
    row_id = serializers.IntegerField(required=False)


class BuilderContextSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["app_builder"], default="app_builder")
    application_id = serializers.IntegerField()
    page_id = serializers.IntegerField()
    element_id = serializers.IntegerField(required=False)


class DashboardContextSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["dashboard"], default="dashboard")
    dashboard_id = serializers.IntegerField()
    widget_id = serializers.IntegerField(required=False)


class WorkspaceContextSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["workspace"], default="workspace")
    workspace_id = serializers.IntegerField()


class ConfirmationResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["confirmation"], default="confirmation")
    action_id = serializers.CharField(max_length=100)
    value = serializers.BooleanField()


class SelectionResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["selection"], default="selection")
    action_id = serializers.CharField(max_length=100)
    value = serializers.CharField(max_length=100)


class ContextField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Context must be an object")

        context_type = data.get("type")
        serializer_map = {
            "database": DatabaseContextSerializer,
            "builder": BuilderContextSerializer,
            "dashboard": DashboardContextSerializer,
            "workspace": WorkspaceContextSerializer,
        }

        serializer_class = serializer_map.get(context_type)
        if not serializer_class:
            raise serializers.ValidationError(
                f"Invalid type. Must be one of: {list(serializer_map.keys())}"
            )

        serializer = serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def to_representation(self, value):
        return value


class ActionResponseField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Action response must be an object")

        response_type = data.get("type")
        serializer_map = {
            "confirmation": ConfirmationResponseSerializer,
            "selection": SelectionResponseSerializer,
        }

        serializer_class = serializer_map.get(response_type)
        if not serializer_class:
            raise serializers.ValidationError(
                f"Invalid type. Must be one of: {list(serializer_map.keys())}"
            )

        serializer = serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def to_representation(self, value):
        return value


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=10000)
    workspace_id = serializers.IntegerField()
    selected_tools = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    context = ContextField(required=False, allow_null=True)
    action_response = ActionResponseField(required=False, allow_null=True)


class ChatsRequestSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField()
    limit = serializers.IntegerField(default=100, max_value=100, min_value=1)


class ChatResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    agent_used = serializers.CharField(required=False, allow_null=True)
    reasoning = serializers.CharField(required=False, allow_null=True)
    confidence = serializers.FloatField(required=False, allow_null=True)
    requires_confirmation = serializers.BooleanField(required=False, default=False)
    action = serializers.DictField(required=False, allow_null=True)
    pending_action = serializers.DictField(required=False, allow_null=True)


class StreamingChatChunkSerializer(serializers.Serializer):
    """Serializer for streaming chat response chunks."""

    type = serializers.ChoiceField(
        choices=[
            ("message_start", "Message Start"),
            ("content_delta", "Content Delta"),
            ("action", "Action"),
            ("confirmation_request", "Confirmation Request"),
            ("message_end", "Message End"),
            ("error", "Error"),
        ]
    )
    data = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(required=False)


class ChatMessageSerializer(serializers.Serializer):
    """Serializer for chat messages retrieved from conversation history."""

    id = serializers.CharField()
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()
    timestamp = serializers.DateTimeField()
    additional_kwargs = serializers.DictField(required=False, default=dict)
