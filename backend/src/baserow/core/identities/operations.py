from baserow.core.operations import WorkspaceCoreOperationType
from baserow.core.registries import OperationType


class ListIdentitiesWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_identities"
    object_scope_name = "workspace"


class IdentityOperationType(OperationType):
    context_scope_name = "workspace"


class CreateIdentityOperationType(IdentityOperationType):
    type = "identity.create"


class UpdateIdentityOperationType(IdentityOperationType):
    type = "identity.update"


class DeleteIdentityOperationType(IdentityOperationType):
    type = "identity.delete"
