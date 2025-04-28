from rest_framework import serializers

from baserow.core.mcp.models import MCPEndpoint


class MCPEndpointSerializer(serializers.ModelSerializer):
    """
    Serializes a complete MCP endpoint object.
    """

    workspace_id = serializers.IntegerField(source="workspace.id", read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)

    class Meta:
        model = MCPEndpoint
        fields = (
            "id",
            "name",
            "key",
            "workspace_id",
            "workspace_name",
            "created",
        )
        read_only_fields = ("id", "key", "created")


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

    class Meta:
        model = MCPEndpoint
        fields = ("name",)
