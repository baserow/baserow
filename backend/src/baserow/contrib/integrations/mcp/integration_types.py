from typing import Any, Dict, Optional

from rest_framework import serializers

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application
from baserow.core.registries import ImportExportConfig

from .client import MCPToolDefinition
from .models import (
    MCPAuthType,
    MCPOAuthClientSource,
    MCPServerIntegration,
    MCPServerTool,
)


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
            "definition_hash",
        )
        read_only_fields = fields


# The stored tools with the editor's choices. A tool the server changed since is
# still refused on its first use.
EXPORTED_TOOL_FIELDS = (
    "name",
    "title",
    "description",
    "input_schema",
    "annotations",
    "definition_hash",
    "enabled",
    "changes_data",
    "changed_since_review",
    "removed",
    "order",
)


class MCPServerIntegrationType(IntegrationType):
    type = "mcp_server"
    model_class = MCPServerIntegration

    # OAuth tokens are left out: an imported server must be connected again.
    class SerializedDict(IntegrationDict):
        url: str
        auth_type: str
        auth_header_name: str
        auth_header_value: str
        oauth_client_id: str
        oauth_client_secret: str
        oauth_client_source: str
        tools: list[dict]

    serializer_field_names = [
        "url",
        "auth_type",
        "auth_header_name",
        "auth_header_value",
        "oauth_client_id",
        "oauth_client_secret",
        "oauth_client_source",
        "oauth_connected",
        "oauth_connected_at",
        "tools",
    ]
    serializer_field_overrides = {
        "tools": MCPServerToolSerializer(
            many=True,
            read_only=True,
            help_text="The tools the server listed at the last refresh.",
        ),
        "oauth_connected": serializers.BooleanField(
            read_only=True,
            help_text="Whether an account is connected, for servers using OAuth.",
        ),
        "oauth_client_source": serializers.CharField(
            read_only=True,
            help_text="Who registered the OAuth client: `manual`, `dynamic` or "
            "`metadata_document`.",
        ),
    }
    request_serializer_field_names = [
        "url",
        "auth_type",
        "auth_header_name",
        "auth_header_value",
        "oauth_client_id",
        "oauth_client_secret",
    ]
    request_serializer_field_overrides = {}
    allowed_fields = [
        "url",
        "auth_type",
        "auth_header_name",
        "auth_header_value",
        "oauth_client_id",
        "oauth_client_secret",
        "oauth_client_source",
    ]
    sensitive_fields = ["auth_header_value", "oauth_client_secret"]
    secret_fields = ["auth_header_value", "oauth_client_secret"]
    # A stored credential is never sent to a server or header someone else chose.
    secret_field_dependencies = {
        "auth_header_value": ["url", "auth_header_name"],
        "oauth_client_secret": ["url", "oauth_client_id"],
    }
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
        A new URL is another server: the tools listed for the old one are
        dropped and must be refreshed and turned on again, and its OAuth account
        and the client Baserow registered there are forgotten. A client id an
        editor enters is theirs; clearing it lets Baserow register itself again.
        """

        values = dict(values)
        if "oauth_client_id" in values:
            values["oauth_client_source"] = (
                MCPOAuthClientSource.MANUAL if values["oauth_client_id"] else ""
            )
        if instance is None:
            return super().prepare_values(values, user, application, instance)

        url_changed = "url" in values and values["url"] != instance.url
        client_changed = (
            "oauth_client_id" in values
            and values["oauth_client_id"] != instance.oauth_client_id
        )
        auth_changed = "auth_type" in values and values["auth_type"] != (
            instance.auth_type
        )
        if url_changed:
            instance.tools.all().delete()
            if instance.oauth_client_source != MCPOAuthClientSource.MANUAL:
                values.setdefault("oauth_client_id", "")
                values.setdefault("oauth_client_secret", "")
                values.setdefault("oauth_client_source", "")
        if auth_changed:
            # A credential the server no longer uses is forgotten, so it can't
            # be sent by mistake later or block moving the server.
            if values["auth_type"] != MCPAuthType.HEADER:
                values["auth_header_value"] = ""
            if values["auth_type"] != MCPAuthType.OAUTH:
                values.update(
                    oauth_client_id="", oauth_client_secret="", oauth_client_source=""
                )
        if url_changed or client_changed or auth_changed:
            instance.clear_oauth_tokens()
            instance.oauth_server = {}
        return super().prepare_values(values, user, application, instance)

    def serialize_property(
        self,
        integration: MCPServerIntegration,
        prop_name: str,
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        # A client Baserow registered belongs to this instance's redirect URL;
        # the importing instance registers its own.
        manual = integration.oauth_client_source == MCPOAuthClientSource.MANUAL
        if prop_name in ("oauth_client_id", "oauth_client_source") and not manual:
            return ""
        if prop_name == "oauth_client_secret" and not manual:
            return ""
        if prop_name == "tools":
            return [
                {name: getattr(tool, name) for name in EXPORTED_TOOL_FIELDS}
                for tool in integration.tools.all()
            ]
        return super().serialize_property(
            integration,
            prop_name,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def _import_tool(
        self, integration: MCPServerIntegration, tool: dict, keep_choices: bool
    ) -> MCPServerTool:
        values = {name: tool[name] for name in EXPORTED_TOOL_FIELDS if name in tool}
        if not keep_choices:
            values.update(enabled=False, changed_since_review=False)
        # Hashed again from what is imported: the call-time check compares the
        # server's definition with this, and a file can't vouch for itself.
        values["definition_hash"] = MCPToolDefinition(
            name=values["name"],
            title=values.get("title", ""),
            description=values.get("description", ""),
            input_schema=values.get("input_schema", {}),
            annotations=values.get("annotations"),
        ).definition_hash
        return MCPServerTool(integration=integration, **values)

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
        # Exports leave the credentials out.
        for name in ("auth_header_value", "oauth_client_secret"):
            if serialized_values.get(name) is None:
                serialized_values[name] = ""
        serialized_values.setdefault("auth_type", MCPAuthType.HEADER)
        serialized_values.setdefault("oauth_client_id", "")
        serialized_values.setdefault("oauth_client_source", "")
        tools = serialized_values.pop("tools", None) or []
        integration = super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
        # Only an internal copy keeps which tools are on. An export file or a
        # template may come from anyone, so its tools wait for a review here.
        keep_choices = bool(
            import_export_config
            and import_export_config.is_duplicate
            and not import_export_config.is_template
        )
        MCPServerTool.objects.bulk_create(
            self._import_tool(integration, tool, keep_choices) for tool in tools
        )
        return integration
