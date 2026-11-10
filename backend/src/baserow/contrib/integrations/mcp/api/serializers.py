from rest_framework import serializers


class MCPToolSettingsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    enabled = serializers.BooleanField(required=False)
    changes_data = serializers.BooleanField(required=False)
    definition_hash = serializers.CharField(
        max_length=64,
        required=False,
        help_text="The definition reviewed. A tool that changed since is left "
        "unchanged.",
    )


class MCPToolsUpdateSerializer(serializers.Serializer):
    tools = MCPToolSettingsSerializer(many=True)


class MCPServerOAuthStartSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()


class MCPServerOAuthCompleteSerializer(serializers.Serializer):
    state = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, default="")
