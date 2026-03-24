from baserow.core.operations import (
    ApplicationOperationType,
    CoreOperationType,
    WorkspaceCoreOperationType,
)


class ManageInstanceAIProvidersOperationType(CoreOperationType):
    type = "instance.manage_ai_providers"


class ManageWorkspaceAIProvidersOperationType(WorkspaceCoreOperationType):
    type = "workspace.manage_ai_providers"


class ManageApplicationAIProvidersOperationType(ApplicationOperationType):
    type = "application.manage_ai_providers"
