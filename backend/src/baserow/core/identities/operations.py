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


class BindIdentityOperationType(IdentityOperationType):
    type = "identity.bind"


class CreateScopedIdentityOperationType(IdentityOperationType):
    """
    Creating an identity with no workspace access and a role on only some
    applications the user may change, as a template install does for its Agents.
    It never reaches more than the user can, so builders may, unlike creating or
    managing identities.
    """

    type = "identity.create_scoped"
