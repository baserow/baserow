from typing import TYPE_CHECKING, Any, Dict, Optional, Type
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage

from rest_framework.exceptions import PermissionDenied

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.mixins import BuilderInstanceWithFormulaMixin
from baserow.contrib.builder.workflow_actions.exceptions import (
    InvalidWorkflowActionEvent,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.core.models import Workspace
from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.registries import WorkflowActionType

if TYPE_CHECKING:
    from baserow.contrib.builder.data_sources.builder_dispatch_context import (
        BuilderDispatchContext,
    )


class BuilderWorkflowActionType(
    WorkflowActionType, PublicCustomFieldsInstanceMixin, BuilderInstanceWithFormulaMixin
):
    allowed_fields = ["order", "page", "page_id", "element", "element_id", "event"]

    parent_property_name = "page"
    id_mapping_name = "builder_workflow_actions"

    def is_deactivated(self, workspace: Workspace) -> bool:
        """
        Returns whether this workflow action type is deactivated for the workspace.
        """

        return False

    def raise_if_deactivated(self, workspace: Workspace) -> None:
        if self.is_deactivated(workspace):
            raise PermissionDenied("This workflow action type is deactivated.")

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: BuilderWorkflowAction = None,
    ):
        from baserow.contrib.builder.elements.handler import ElementHandler

        if "element_id" in values:
            values["element"] = ElementHandler().get_element(values["element_id"])

        if "event" in values:
            element = values.get("element", instance.element if instance else None)
            self.validate_event(values["event"], element)

        return super().prepare_values(values, user, instance)

    def export_prepared_values(self, instance: BuilderWorkflowAction) -> Dict[str, Any]:
        """
        Returns a JSON-serializable dict of the action's prepared values, so an
        update can be undone/redone by re-applying them. Formula fields are stored
        as their serialized dicts. The `page`/`element` relations are skipped: their
        `page_id`/`element_id` counterparts (also allowed fields) capture them in a
        JSON-serializable way.
        """

        return {
            key: getattr(instance, key)
            for key in self.allowed_fields
            if key not in ("page", "element")
        }

    def validate_event(self, event: str, element: Optional[Element]) -> None:
        """
        Ensures that the given event is one the element can fire. Every element
        type declares its events in `ElementType.get_event_names()`. Workflow
        actions which aren't attached to an element can only use the static
        `EventTypes`.

        :param event: The event to validate.
        :param element: The element the workflow action is attached to, if any.
        :raises InvalidWorkflowActionEvent: If the event can never be fired.
        """

        element_type_name = None
        if element is None:
            valid_events = [e.value for e in EventTypes]
        else:
            element = element.specific
            element_type = element_type_registry.get_by_model(element.specific_class)
            element_type_name = element_type.type
            valid_events = element_type.get_event_names(element)

        if event not in valid_events:
            raise InvalidWorkflowActionEvent(event, valid_events, element_type_name)

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ) -> Type[BuilderWorkflowAction]:
        """
        Responsible for ensuring that when a new workflow action is created from a
        serialized value, if the event points to a collection field (as opposed to an
        element), the event's `uid` is migrated from the serialized value to the
        corresponding `uid` in the `id_mapping` dict.

        :param serialized_values: The serialized values for the new workflow action.
        :param id_mapping: The mapping of old to new ids.
        :param files_zip: An optional zip file for the related files.
        :param storage: The storage instance.
        :param cache: An optional cache dict.
        :param kwargs: Additional keyword arguments.
        :return: The new workflow action instance.
        """

        event = serialized_values["event"]
        if BuilderWorkflowAction.is_dynamic_event(event):
            # Dynamic events have the shape `<uid>_<event>`, where `<uid>` is the
            # uid of a collection field / menu item that was regenerated during
            # the import. Values which do not follow that shape, or whose uid is
            # unknown, are kept untouched: such an action can never be fired, but
            # it must not prevent the whole application from being imported.
            exported_uid, separator, exported_event = event.partition("_")
            uid_mapping = id_mapping.get("builder_element_event_uids", {})
            if separator and exported_uid in uid_mapping:
                imported_uid = uid_mapping[exported_uid]
                serialized_values["event"] = f"{imported_uid}_{exported_event}"

        return super().create_instance_from_serialized(
            serialized_values, id_mapping, files_zip, storage, cache
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        """
        This hooks allow to customize the deserialization of a property.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        # Migrate page id
        if prop_name == "page_id":
            return id_mapping["builder_pages"].get(value)

        # Migrate element id
        if prop_name == "element_id":
            return id_mapping["builder_page_elements"][value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip=None,
        storage=None,
        cache: Dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        from baserow.contrib.builder.elements.handler import ElementHandler

        if cache is None:
            cache = {}

        element_id = serialized_values["element_id"]
        import_context = {}
        if element_id:
            imported_element_id = id_mapping["builder_page_elements"][element_id]
            import_context = ElementHandler().get_import_context_addition(
                imported_element_id, cache.get("imported_element_map", None)
            )

        created_instance = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip,
            storage,
            cache,
            **(kwargs | import_context),
        )

        updated_models = self.import_formulas(
            created_instance, id_mapping, import_formula, **(kwargs | import_context)
        )

        [m.save() for m in updated_models]

        return created_instance

    def dispatch(
        self,
        workflow_action: WorkflowAction,
        dispatch_context: "BuilderDispatchContext",
    ) -> DispatchResult:
        raise InvalidServiceTypeDispatchSource("This service cannot be dispatched.")


class BuilderWorkflowActionTypeRegistry(
    Registry, ModelRegistryMixin, CustomFieldsRegistryMixin
):
    """
    Contains all the registered workflow action types for the builder module.
    """

    name = "builder_workflow_action_type"


builder_workflow_action_type_registry = BuilderWorkflowActionTypeRegistry()
