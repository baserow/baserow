from typing import Any, Dict, Optional

from rest_framework import serializers

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application
from baserow.core.registries import ImportExportConfig

from .models import MCPServerIntegration, MCPServerTool


class MCPServerToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = MCPServerTool
        fields = (
            "name",
            "title",
            "description",
            "annotations",
            "enabled",
            "changes_data",
            "changed_since_review",
            "removed",
        )
        read_only_fields = fields


class MCPServerIntegrationType(IntegrationType):
    type = "mcp_server"
    model_class = MCPServerIntegration

    class SerializedDict(IntegrationDict):
        url: str
        auth_header_name: str
        auth_header_value: str

    serializer_field_names = ["url", "auth_header_name", "auth_header_value", "tools"]
    serializer_field_overrides = {
        "tools": MCPServerToolSerializer(
            many=True,
            read_only=True,
            help_text="The tools the server listed at the last refresh.",
        )
    }
    request_serializer_field_names = ["url", "auth_header_name", "auth_header_value"]
    request_serializer_field_overrides = {}
    allowed_fields = ["url", "auth_header_name", "auth_header_value"]
    sensitive_fields = ["auth_header_value"]
    secret_fields = ["auth_header_value"]
    # A stored credential is never sent to a server or header someone else chose.
    secret_field_dependencies = {"auth_header_value": ["url", "auth_header_name"]}
    serializer_field_extra_kwargs = {
        "auth_header_value": {
            "help_text": "The credential sent in the auth header. Write-only: it "
            "is never returned, see `has_auth_header_value`. Omit it on an update "
            "to keep the stored value."
        }
    }

    def supports_application_type(self, application_type) -> bool:
        # Only Agents call MCP tools for now.
        return application_type.type == "agent"

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related("tools")

    def prepare_values(
        self,
        values: Dict[str, Any],
        user,
        application: Optional[Application] = None,
        instance: Optional[MCPServerIntegration] = None,
    ) -> Dict[str, Any]:
        """
        A new URL is another server, so the tools listed for the old one are
        dropped and must be refreshed and turned on again.
        """

        if instance is not None and "url" in values and values["url"] != instance.url:
            instance.tools.all().delete()
        return super().prepare_values(values, user, application, instance)

    def import_serialized(
        self,
        application: Application,
        serialized_values: Dict[str, Any],
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
        import_export_config: Optional[ImportExportConfig] = None,
    ) -> MCPServerIntegration:
        # Exports leave the credential out.
        if serialized_values.get("auth_header_value") is None:
            serialized_values["auth_header_value"] = ""
        return super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
