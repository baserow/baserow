from rest_framework import serializers


class WhiteboardContentSerializer(serializers.Serializer):
    content = serializers.JSONField(
        required=True,
        help_text=(
            "The complete Excalidraw scene state stored as a JSON object "
            "(typically `{ elements, appState, files }`)."
        ),
    )
