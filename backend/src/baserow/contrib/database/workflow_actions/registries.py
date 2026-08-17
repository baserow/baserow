from typing import TYPE_CHECKING, Any, Dict

from baserow.contrib.database.formula_importer import import_formula
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.core.deferred_callbacks import register_deferred_callback
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.services.exceptions import (
    InvalidServiceTypeDispatchSource,
)
from baserow.core.workflow_actions.registries import WorkflowActionType

if TYPE_CHECKING:
    pass


class DatabaseWorkflowActionType(WorkflowActionType, CustomFieldsInstanceMixin):
    allowed_fields = ["order", "field", "field_id"]
    parent_property_name = "field"
    id_mapping_name = "database_workflow_actions"

    # Set to True by a type the browser runs itself, which the dispatch then
    # hands back instead of running server side.
    is_frontend_only = False

    class SerializedDict(DatabaseWorkflowActionDict):
        pass

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}

    def dispatch(self, workflow_action, dispatch_context):
        raise InvalidServiceTypeDispatchSource(
            "This workflow action type cannot be dispatched."
        )

    def import_serialized(
        self,
        parent,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Imports the action, then defers remapping the field references inside
        its formulas, such as `get('fields.field_25')` or `get('row.field_25')`.

        `deserialize_property` only reaches the FK-shaped references, so without
        this a duplicated table keeps formulas naming the original table's
        fields and silently reads the wrong ones (ADR 006 section 6). Deferred
        because a formula can name a field of an application not imported yet.
        """

        created_instance = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip,
            storage,
            cache,
            **kwargs,
        )

        def import_action_formulas():
            # `id_mapping` is the same dict throughout an import, so by now it
            # holds every application's ids.
            updated_models = self.import_formulas(
                created_instance, id_mapping, import_formula, **kwargs
            )
            for updated_model in updated_models:
                updated_model.save()

        register_deferred_callback(import_action_formulas)

        return created_instance


class DatabaseWorkflowActionTypeRegistry(
    Registry, ModelRegistryMixin, CustomFieldsRegistryMixin
):
    """
    Contains all the registered workflow action types for the database module.
    """

    name = "database_workflow_action_type"


database_workflow_action_type_registry = DatabaseWorkflowActionTypeRegistry()
