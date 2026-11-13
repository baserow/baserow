class MCPServerUnreachable(Exception):
    """The MCP server could not be reached, or failed while listing its tools."""


class MCPServerRefusedCredential(MCPServerUnreachable):
    """The MCP server answered 401 or 403: the key or account isn't accepted."""


class MCPServerNotConnected(Exception):
    """The MCP server uses OAuth and no account is connected, or it expired."""


class MCPServerCredentialUnavailable(MCPServerNotConnected):
    """
    A credential of the MCP server is stored but none of the configured
    encryption keys can read it. It's kept for when the key is back.
    """


class MCPOAuthFailed(Exception):
    """An OAuth step with the MCP server's authorization server failed."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        # The server was down or overloaded: the same request may work later.
        self.retryable = retryable


class MCPOAuthStateInvalid(Exception):
    """The OAuth callback doesn't match an authorization Baserow started."""


class MCPServerDoesNotUseOAuth(Exception):
    """A sign-in was started for a server that doesn't use OAuth."""
