from abc import ABC

from baserow.core.operations import ApplicationOperationType
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
