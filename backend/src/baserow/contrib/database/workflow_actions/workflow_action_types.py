from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
    UpdateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
    DatabaseWorkflowServiceActionType,
)
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.formula.serializers import FormulaSerializerField


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


class OpenUrlWorkflowActionType(DatabaseWorkflowActionType):
    type = "open_url"
    model_class = OpenUrlWorkflowAction
    is_frontend_only = True

    allowed_fields = DatabaseWorkflowActionType.allowed_fields + ["url", "target"]
    serializer_field_names = ["url", "target"]
    serializer_field_overrides = {
        "url": FormulaSerializerField(
            help_text="The URL to open, as a formula.",
            required=False,
        ),
    }

    class SerializedDict(DatabaseWorkflowActionDict):
        url: str
        target: str
