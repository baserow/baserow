from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.mixins import BuilderInstanceWithFormulaMixin
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)
from baserow.core.workflow_actions.registries import WorkflowActionType


class BuilderWorkflowActionType(
    WorkflowActionType, PublicCustomFieldsInstanceMixin, BuilderInstanceWithFormulaMixin
):
    allowed_fields = ["order", "page", "page_id", "element", "element_id", "event"]

    parent_property_name = "page"
    id_mapping_name = "builder_workflow_actions"

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: BuilderWorkflowAction = None,
    ):
        from baserow.contrib.builder.elements.handler import ElementHandler

        if "element_id" in values:
            values["element"] = ElementHandler().get_element(values["element_id"])

        return super().prepare_values(values, user, instance)

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
            return id_mapping["builder_pages"][value]

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


class BuilderWorkflowActionTypeRegistry(
    Registry, ModelRegistryMixin, CustomFieldsRegistryMixin
):
    """
    Contains all the registered workflow action types for the builder module.
    """

    name = "builder_workflow_action_type"


builder_workflow_action_type_registry = BuilderWorkflowActionTypeRegistry()
