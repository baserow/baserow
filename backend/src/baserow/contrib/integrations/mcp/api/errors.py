ERROR_MCP_SERVER_UNREACHABLE = (
    "ERROR_MCP_SERVER_UNREACHABLE",
    400,
    "The MCP server could not be reached or failed to list its tools.",
)

ERROR_MCP_SERVER_REFUSED_CREDENTIAL = (
    "ERROR_MCP_SERVER_REFUSED_CREDENTIAL",
    400,
    "The MCP server refused the API key or the connected account.",
)
ERROR_MCP_SERVER_NOT_CONNECTED = (
    "ERROR_MCP_SERVER_NOT_CONNECTED",
    400,
    "The MCP server uses OAuth and no account is connected.",
)
ERROR_MCP_OAUTH_FAILED = ("ERROR_MCP_OAUTH_FAILED", 400, "{e.message}")
ERROR_MCP_OAUTH_STATE_INVALID = (
    "ERROR_MCP_OAUTH_STATE_INVALID",
    400,
    "This sign-in expired or was started by someone else. Try connecting again.",
)
ERROR_MCP_SERVER_DOES_NOT_USE_OAUTH = (
    "ERROR_MCP_SERVER_DOES_NOT_USE_OAUTH",
    400,
    "The MCP server doesn't use OAuth sign-in.",
)
