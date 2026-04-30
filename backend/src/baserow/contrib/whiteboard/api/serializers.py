from rest_framework import serializers


class WhiteboardContentSerializer(serializers.Serializer):
    content = serializers.JSONField(
        required=True,
        help_text=(
            "The complete Excalidraw scene state stored as a JSON object "
            "(typically `{ elements, appState, files }`)."
        ),
    )


class BroadcastChangesSerializer(serializers.Serializer):
    payload = serializers.JSONField(
        required=True,
        help_text=(
            "An opaque JSON payload that will be broadcast to every other client "
            "subscribed to this whiteboard. Used for ephemeral collaboration "
            "messages such as scene updates and pointer movements; nothing is "
            "persisted server-side."
        ),
    )
