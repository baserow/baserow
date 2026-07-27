from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DeleteRowWorkflowAction,
    UpdateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowServiceActionType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
    LocalBaserowUpsertRowServiceType,
)


class CreateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "create_row"
    model_class = CreateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class UpdateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "update_row"
    model_class = UpdateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class DeleteRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "delete_row"
    model_class = DeleteRowWorkflowAction
    service_type = LocalBaserowDeleteRowServiceType.type
