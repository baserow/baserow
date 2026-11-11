from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import mcp_tool_registry


class AllowedToolsField(serializers.ListField):
    """
    A non-empty list of unique tool names. Whether the endpoint can use them is
    checked by the handler.
    """

    def __init__(self, **kwargs):
        super().__init__(child=serializers.CharField(), allow_empty=False, **kwargs)

    def to_internal_value(self, data):
        names = super().to_internal_value(data)
        if len(set(names)) != len(names):
            raise serializers.ValidationError("Tools must be unique.")
        return names


class MCPEndpointSerializer(serializers.ModelSerializer):
    """
    Serializes a complete MCP endpoint object.
    """

    workspace_id = serializers.IntegerField(source="workspace.id", read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    allowed_tools = serializers.SerializerMethodField()

    class Meta:
        model = MCPEndpoint
        fields = (
            "id",
            "name",
            "key",
            "workspace_id",
            "workspace_name",
            "allowed_tools",
            "created",
        )
        read_only_fields = ("id", "key", "created")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_allowed_tools(self, endpoint):
        return mcp_tool_registry.get_allowed_names(endpoint)


class CreateMCPEndpointSerializer(serializers.ModelSerializer):
    """
    Used for validating the creation of a new MCP endpoint.
    """

    workspace_id = serializers.IntegerField()

    class Meta:
        model = MCPEndpoint
        fields = ("name", "workspace_id")


class UpdateMCPEndpointSerializer(serializers.ModelSerializer):
    """
    Used for validating updating an existing MCP endpoint.
    """

    allowed_tools = AllowedToolsField(required=False)

    class Meta:
        model = MCPEndpoint
        fields = ("name", "allowed_tools")
        extra_kwargs = {"name": {"required": False}}

    def validate(self, data):
        if not data:
            raise serializers.ValidationError(
                "Provide the name or allowed_tools to change."
            )
        return data


class UpdateAllowedToolsSerializer(serializers.Serializer):
    allowed_tools = AllowedToolsField()
