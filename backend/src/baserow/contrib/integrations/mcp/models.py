from django.db import models

from baserow.core.integrations.models import Integration


class MCPServerIntegration(Integration):
    """A remote MCP server reached over Streamable HTTP."""

    url = models.URLField(
        max_length=2000,
        help_text="The Streamable HTTP endpoint of the MCP server.",
    )
    auth_header_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_default="",
        help_text="The header that carries the credential, e.g. Authorization.",
    )
    auth_header_value = models.TextField(
        blank=True,
        default="",
        db_default="",
        help_text="The credential sent in the auth header, e.g. Bearer <token>.",
    )


class MCPServerTool(models.Model):
    """
    A tool the server listed when its tools were last refreshed. Only tools an
    editor turned on are offered, and only while the server still describes them
    the same way: a changed definition turns the tool off until it is reviewed.
    """

    integration = models.ForeignKey(
        MCPServerIntegration, on_delete=models.CASCADE, related_name="tools"
    )
    name = models.CharField(max_length=128)
    title = models.CharField(max_length=255, blank=True, default="", db_default="")
    description = models.TextField(blank=True, default="", db_default="")
    input_schema = models.JSONField(default=dict)
    annotations = models.JSONField(null=True)
    definition_hash = models.CharField(max_length=64)
    enabled = models.BooleanField(default=False, db_default=False)
    # The server's own read-only hint can't be trusted, so every tool counts as
    # changing data until an editor says otherwise.
    changes_data = models.BooleanField(default=True, db_default=True)
    # Set when the server changed a tool that was turned on, cleared on review.
    changed_since_review = models.BooleanField(default=False, db_default=False)
    removed = models.BooleanField(default=False, db_default=False)
    order = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["integration", "name"], name="mcp_server_tool_unique_name"
            )
        ]
