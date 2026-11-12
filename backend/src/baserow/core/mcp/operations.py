from abc import ABC

from baserow.core.operations import WorkspaceCoreOperationType


class CreateMCPEndpointOperationType(WorkspaceCoreOperationType):
    type = "workspace.create_mcp_endpoint"


class MCPEndpointOperationType(WorkspaceCoreOperationType, ABC):
    """
    Checked against the endpoint's workspace: endpoints belong to one user, and a
    member with a role only on a database or table gets the read only role on the
    workspace, not on the endpoints inside it.
    """


class ReadMCPEndpointOperationType(MCPEndpointOperationType):
    type = "workspace.mcp_endpoint.read"


class UpdateMCPEndpointOperationType(MCPEndpointOperationType):
    type = "workspace.mcp_endpoint.update"


class DeleteMCPEndpointOperationType(MCPEndpointOperationType):
    type = "workspace.mcp_endpoint.delete"
