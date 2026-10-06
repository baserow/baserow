from rest_framework import serializers

from baserow.core.mcp.registries import mcp_tool_registry


class ConsentSerializer(serializers.Serializer):
    query = serializers.CharField()
    allow = serializers.BooleanField()
    workspace_id = serializers.IntegerField(required=False)
    tools = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, data):
        if not data["allow"]:
            return data

        if "workspace_id" not in data:
            raise serializers.ValidationError(
                {"workspace_id": "This field is required when allowing."}
            )

        tools = data.get("tools")
        if not tools:
            raise serializers.ValidationError(
                {"tools": "Select at least one tool when allowing."}
            )
        if len(set(tools)) != len(tools):
            raise serializers.ValidationError({"tools": "Tools must be unique."})

        enabled = [tool.name for tool in mcp_tool_registry.get_enabled_tools()]
        unknown = sorted(set(tools) - set(enabled))
        if unknown:
            raise serializers.ValidationError(
                {"tools": f"Unknown tools: {', '.join(unknown)}."}
            )

        # Stored in registry order so the grant doesn't depend on the client's.
        requested = set(tools)
        data["tools"] = [name for name in enabled if name in requested]
        return data
