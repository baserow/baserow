from django.conf import settings
from django.db import models

from baserow.core.fields import EncryptedTextField
from baserow.core.integrations.models import Integration


class MCPAuthType(models.TextChoices):
    NONE = "none"
    HEADER = "header"
    OAUTH = "oauth"


class MCPOAuthClientSource(models.TextChoices):
    # The editor registered Baserow with the authorization server themselves.
    MANUAL = "manual"
    # Baserow registered itself through dynamic client registration.
    DYNAMIC = "dynamic"
    # The client id is Baserow's client metadata document URL.
    METADATA_DOCUMENT = "metadata_document"


# Locks an MCP server through its integration row only. Integration updates
# lock that row before writing the MCP one, so taking both here could deadlock.
MCP_SERVER_LOCK_OF = ("integration_ptr",)


class MCPServerIntegration(Integration):
    """
    A remote MCP server reached over Streamable HTTP. It authenticates with a
    static header, or with OAuth: one account connected by an editor and used by
    every conversation with the Agent.
    """

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
    auth_header_value = EncryptedTextField(
        blank=True,
        default="",
        db_default="",
        help_text="The credential sent in the auth header, e.g. Bearer <token>.",
    )
    auth_type = models.CharField(
        max_length=16,
        choices=MCPAuthType.choices,
        default=MCPAuthType.HEADER,
        db_default=MCPAuthType.HEADER,
    )
    oauth_client_id = models.CharField(
        max_length=2000,
        blank=True,
        default="",
        db_default="",
        help_text="The OAuth client id, entered by an editor or registered by Baserow.",
    )
    oauth_client_secret = EncryptedTextField(
        blank=True, default="", db_default="", help_text="The OAuth client secret."
    )
    oauth_client_source = models.CharField(
        max_length=32,
        choices=MCPOAuthClientSource.choices,
        blank=True,
        default="",
        db_default="",
    )
    # What discovery found: issuer, token endpoint, how to authenticate to it,
    # the resource indicator and the scope. Kept to refresh tokens later.
    oauth_server = models.JSONField(default=dict, db_default={})
    oauth_access_token = EncryptedTextField(blank=True, default="", db_default="")
    oauth_refresh_token = EncryptedTextField(blank=True, default="", db_default="")
    oauth_expires_at = models.DateTimeField(null=True, blank=True)
    oauth_connected_at = models.DateTimeField(null=True, blank=True)
    oauth_generation = models.PositiveIntegerField(
        default=0,
        db_default=0,
        help_text="Changes when the server is set up differently or signed out, "
        "so a sign-in started before can tell.",
    )
    oauth_connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    @property
    def oauth_connected(self) -> bool:
        return bool(self.oauth_access_token)

    def clear_oauth_tokens(self):
        self.oauth_access_token = ""
        self.oauth_refresh_token = ""
        self.oauth_expires_at = None
        self.oauth_connected_at = None
        self.oauth_connected_by = None


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
    # From the server's read-only hint: a tool without it counts as changing data.
    changes_data = models.BooleanField(default=True, db_default=True)
    # Whether a call waits for the conversation owner's approval. On until an
    # editor turns it off: the server's tools run with its own credential.
    ask_first = models.BooleanField(default=True, db_default=True)
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
