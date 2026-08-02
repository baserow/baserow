from baserow.contrib.database.fields.formula_visitors import (
    replace_field_id_references,
)
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
from baserow.core.formula import BaserowFormulaException
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BaserowFormulaObject


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

    def deserialize_property(
        self,
        prop_name,
        value,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        if prop_name == "url" and value:
            try:
                # Assign the whole object, not just the formula string: saving a
                # bare string makes `to_python` re-wrap it as `simple` mode,
                # which turns a raw literal URL into an unparseable formula.
                url_formula = BaserowFormulaObject.to_formula(value)
                return {
                    **url_formula,
                    "formula": replace_field_id_references(
                        url_formula, id_mapping["database_fields"]
                    ),
                }
            except (KeyError, BaserowFormulaException):
                # Missing mapping / unparseable formula: keep as-is so the
                # import succeeds; broken state surfaces via `error`.
                return value

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )
