from abc import ABC

from baserow.core.operations import ApplicationOperationType, WorkspaceCoreOperationType
from baserow.core.registries import OperationType


class ListIntegrationsApplicationOperationType(ApplicationOperationType):
    type = "application.list_integrations"
    object_scope_name = "integration"


class OrderIntegrationsOperationType(ApplicationOperationType):
    type = "application.order_integrations"
    object_scope_name = "integration"


class CreateIntegrationOperationType(ApplicationOperationType):
    type = "application.create_integration"


class IntegrationOperationType(OperationType, ABC):
    context_scope_name = "integration"


class DeleteIntegrationOperationType(IntegrationOperationType):
    type = "application.integration.delete"


class UpdateIntegrationOperationType(IntegrationOperationType):
    type = "application.integration.update"


class ReadIntegrationOperationType(IntegrationOperationType):
    type = "application.integration.read"


class RestoreIntegrationOperationType(IntegrationOperationType):
    type = "application.integration.restore"


# The workspace integrations are owned by the shared application of the workspace.
# The operations above would resolve through it to the workspace, so that anyone
# allowed to manage the integrations of every application of the workspace could
# manage them. These are checked instead, see `IntegrationService`.


class ListIntegrationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_integrations"
    object_scope_name = "integration"


class OrderIntegrationsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.order_integrations"
    object_scope_name = "integration"


class CreateIntegrationWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.create_integration"


class DeleteWorkspaceIntegrationOperationType(IntegrationOperationType):
    type = "workspace.integration.delete"


class UpdateWorkspaceIntegrationOperationType(IntegrationOperationType):
    type = "workspace.integration.update"


class RestoreWorkspaceIntegrationOperationType(IntegrationOperationType):
    type = "workspace.integration.restore"
