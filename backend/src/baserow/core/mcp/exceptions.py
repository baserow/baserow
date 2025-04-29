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
