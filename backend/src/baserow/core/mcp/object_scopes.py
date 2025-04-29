from django.db.models import Q

from baserow.core.mcp.models import MCPEndpoint
from baserow.core.object_scopes import WorkspaceObjectScopeType
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class MCPEndpointObjectScopeType(ObjectScopeType):
    type = "mcp_endpoint"
    model_class = MCPEndpoint

    def get_parent_scope(self):
        return object_scope_type_registry.get("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
