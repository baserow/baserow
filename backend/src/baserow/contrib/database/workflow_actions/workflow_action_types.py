from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
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


class LocalBaserowCreateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_create_row"
    model_class = LocalBaserowCreateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowUpdateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_update_row"
    model_class = LocalBaserowUpdateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowDeleteRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_delete_row"
    model_class = LocalBaserowDeleteRowWorkflowAction
    service_type = LocalBaserowDeleteRowServiceType.type


class OpenUrlWorkflowActionType(DatabaseWorkflowActionType):
    type = "open_url"
    model_class = OpenUrlWorkflowAction
    is_frontend_only = True

    allowed_fields = DatabaseWorkflowActionType.allowed_fields + ["url", "target"]
    serializer_field_names = ["url", "target"]
    # Remapped on import by the deferred pass in `DatabaseWorkflowActionType`.
    simple_formula_fields = ["url"]
    serializer_field_overrides = {
        "url": FormulaSerializerField(
            help_text="The URL to open, as a formula.",
            required=False,
        ),
    }

    class SerializedDict(DatabaseWorkflowActionDict):
        url: str
        target: str
