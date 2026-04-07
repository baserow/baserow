from abc import ABC

from baserow.core.registries import OperationType


class CoreOperationType(OperationType, ABC):
    context_scope_name = "core"


class UpdateSettingsOperationType(CoreOperationType):
    type = "settings.update"


class CreateWorkspaceOperationType(CoreOperationType):
    type = "create_workspace"


class ListWorkspacesOperationType(CoreOperationType):
    type = "list_workspaces"
    object_scope_name = "workspace"


class WorkspaceCoreOperationType(CoreOperationType, ABC):
    context_scope_name = "workspace"


class ReadWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.read"


class UpdateWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.update"


class DeleteWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.delete"


class ExportWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.export"


class RestoreWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.restore"


class ListApplicationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_applications"
    object_scope_name = "application"


class CreateApplicationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.create_application"


class OrderApplicationsOperationType(WorkspaceCoreOperationType):
    type = "workspace.order_applications"
    object_scope_name = "application"


class CreateInvitationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.create_invitation"


class ListInvitationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_invitations"
    object_scope_name = "workspace_invitation"


class ListWorkspaceUsersWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_workspace_users"
    object_scope_name = "workspace_user"


class InvitationWorkspaceOperationType(CoreOperationType, ABC):
    context_scope_name = "workspace_invitation"


class ReadInvitationWorkspaceOperationType(InvitationWorkspaceOperationType):
    type = "invitation.read"


class UpdateWorkspaceInvitationType(InvitationWorkspaceOperationType):
    type = "invitation.update"


class DeleteWorkspaceInvitationOperationType(InvitationWorkspaceOperationType):
    type = "invitation.delete"


class WorkspaceUserOperationType(OperationType, ABC):
    context_scope_name = "workspace_user"


class UpdateWorkspaceUserOperationType(WorkspaceUserOperationType):
    type = "workspace_user.update"


class DeleteWorkspaceUserOperationType(WorkspaceUserOperationType):
    type = "workspace_user.delete"


class ApplicationOperationType(OperationType, ABC):
    context_scope_name = "application"


class ReadApplicationOperationType(ApplicationOperationType):
    type = "application.read"


class UpdateApplicationOperationType(ApplicationOperationType):
    type = "application.update"


class DuplicateApplicationOperationType(ApplicationOperationType):
    type = "application.duplicate"


class DeleteApplicationOperationType(ApplicationOperationType):
    type = "application.delete"


class RestoreApplicationOperationType(ApplicationOperationType):
    type = "application.restore"
