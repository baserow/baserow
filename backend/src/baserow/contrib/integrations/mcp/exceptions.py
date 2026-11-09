class MCPServerUnreachable(Exception):
    """The MCP server could not be reached, or failed while listing its tools."""


class MCPServerRefusedCredential(MCPServerUnreachable):
    """The MCP server answered 401 or 403: the key or account isn't accepted."""


class MCPServerNotConnected(Exception):
    """The MCP server uses OAuth and no account is connected, or it expired."""


class MCPOAuthFailed(Exception):
    """An OAuth step with the MCP server's authorization server failed."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MCPOAuthStateInvalid(Exception):
    """The OAuth callback doesn't match an authorization Baserow started."""
