from baserow.core.tools.errors import (  # noqa: F401
    INTERNAL_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    PERMISSION_DENIED_MESSAGE,
    ToolInputError,
    flatten_error_detail,
    format_validation_error,
)
from baserow.core.tools.errors import tool_error_message as to_mcp_error  # noqa: F401


class MCPEndpointDoesNotExist(Exception):
    """Raised when trying to get an MCP endpoint that doesn't exist."""


class MCPEndpointDoesNotBelongToUser(Exception):
    """
    Raised when a user tries to access an MCP endpoint that doesn't belong to them.
    """


class MaximumUniqueEndpointTriesError(Exception):
    """
    Raised when the maximum amount of tries has been exceeded when generating a
    unique MCP endpoint key.
    """


class MCPToolsNotAvailable(Exception):
    """Raised when an endpoint is given tools it can't use."""

    def __init__(self, names: list[str]):
        self.names = names
        super().__init__(f"Tools not available: {', '.join(names)}.")


# The tools MCP serves are shared, so their input errors are too.
MCPToolInputError = ToolInputError
