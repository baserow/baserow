from baserow.core.operations import WorkspaceCoreOperationType


class ListWorkspaceSkillsOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_skills"


class CreateWorkspaceSkillOperationType(WorkspaceCoreOperationType):
    type = "workspace.create_skill"


class UpdateWorkspaceSkillOperationType(WorkspaceCoreOperationType):
    type = "workspace.update_skill"


class DeleteWorkspaceSkillOperationType(WorkspaceCoreOperationType):
    type = "workspace.delete_skill"
