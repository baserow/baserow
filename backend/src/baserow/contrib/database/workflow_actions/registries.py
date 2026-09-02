from typing import TYPE_CHECKING, Any, Dict, Optional
from zipfile import ZipFile

from django.core.files.storage import Storage

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
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.registries import WorkflowActionType

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class DatabaseWorkflowActionType(WorkflowActionType, CustomFieldsInstanceMixin):
    allowed_fields = ["order", "field", "field_id"]
    parent_property_name = "field"
    id_mapping_name = "database_workflow_actions"

    # Set to True by a type the browser runs itself, which the dispatch then
    # hands back instead of running server side.
    is_frontend_only = False

    # Set by a type whose result only a real answer can describe. A row action
    # reads the target table's fields instead.
    captures_sample_data = False

    # Set by a type that reaches outside this installation. Only clicks that
    # contain one spend the rate limit's budget.
    is_external = False

    class SerializedDict(DatabaseWorkflowActionDict):
        pass

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}

    def get_result_field_names(self, workflow_action: WorkflowAction) -> Dict[str, str]:
        """
        Maps `field_<id>` to the name the dispatch result is keyed by, since it
        is serialized with `user_field_names`. The browser needs it to resolve
        a `previous_action` path in a frontend-only action.

        :param workflow_action: The action whose result this describes.
        :return: The mapping, empty for an action that returns no row.
        """

        return {}

    def result_describes_shape(self, result: DispatchResult) -> bool:
        """
        Whether what the action returned is worth remembering as the shape the
        actions after it read from. Only asked of a type that sets
        `captures_sample_data`, since what a failure looks like is its own: an
        HTTP request answers 404 with an error page and still dispatches.

        :param result: What the action returned.
        :return: True when the result describes the answer's real shape.
        """

        return True

    def dispatch(
        self,
        workflow_action: WorkflowAction,
        dispatch_context: "DatabaseDispatchContext",
    ) -> DispatchResult:
        raise InvalidServiceTypeDispatchSource(
            "This workflow action type cannot be dispatched."
        )

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> WorkflowAction:
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
