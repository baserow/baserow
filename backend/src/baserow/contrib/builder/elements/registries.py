import uuid
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db import models

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.mixins import BuilderInstanceWithFormulaMixin
from baserow.contrib.builder.pages.models import Page
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.models import Workspace
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX
from baserow.core.user_sources.handler import UserSourceHandler

from .models import CollectionField, Element
from .types import ElementDictSubClass, ElementSubClass

BUILDER_PAGE_ELEMENTS = "builder_page_elements"
ELEMENT_IDS_PROCESSED_FOR_ROLES = "_element_ids_processed_for_roles"
EXISTING_USER_SOURCE_ROLES = "_existing_user_source_roles"


class ElementType(
    BuilderInstanceWithFormulaMixin,
    EasyImportExportMixin[ElementSubClass],
    CustomFieldsInstanceMixin,
    ModelInstanceMixin[ElementSubClass],
    Instance,
    ABC,
):
    """Element type"""

    SerializedDict: Type[ElementDictSubClass]
    parent_property_name = "page"
    id_mapping_name = BUILDER_PAGE_ELEMENTS

    # Whether this element is a multi-page element and should be placed on shared page.
    is_multi_page_element = False

    # The order in which this element type is imported in `import_elements`.
    # By default, the priority is `0`, the lowest value. If this property is
    # not overridden, then the instance is imported last.
    import_element_priority = 0

    def is_deactivated(self, workspace: Workspace) -> bool:
        """
        Returns whether this element type is deactivated for the given workspace.
        """

        return False

    def prepare_value_for_db(self, values: Dict, instance: Optional[Element] = None):
        """
        This function allows you to hook into the moment an element is created or
        updated. If the element is updated `instance` will be defined, and you can use
        `instance` to extract any context data that might be required for the
        implementation of this hook.

        :param values: The values that are being updated
        :param instance: (optional) The existing instance that is being updated
        :return:
        """

        from baserow.contrib.builder.elements.handler import ElementHandler

        parent_element_id = values.get(
            "parent_element_id", getattr(instance, "parent_element_id", None)
        )

        if instance:
            place_in_container = values.get(
                "place_in_container", instance.place_in_container
            )
            page = values.get("page", instance.page)
        else:
            place_in_container = values.get("place_in_container", None)
            page = values["page"]

        parent_element = None
        if parent_element_id is not None:
            parent_element = ElementHandler().get_element(parent_element_id)

        # Validate the place for this element
        self.validate_place(page, parent_element, place_in_container)

        return values

    def validate_place(
        self,
        page: Page,
        parent_element: Optional[ElementSubClass],
        place_in_container: str,
    ):
        """
        Validates the page/parent_element/place_in_container for this element.
        Can be overridden to change the behaviour.

        :param page: the page we want to add/move the element to.
        :param parent_element: the parent_element if any.
        :param place_in_container: the place in container in the parent.
        :raises ValidationError: if the the element place is not allowed.
        """

        if parent_element:
            if self.type not in [
                e.type for e in parent_element.get_type().child_types_allowed
            ]:
                raise ValidationError(
                    f"Container of type {parent_element.get_type().type} can't have child of "
                    f"type {self.type}"
                )

            # If we have a parent, we validate the place is accepted by this container.
            parent_element.get_type().validate_place_in_container(
                place_in_container, parent_element
            )
        else:
            if self.is_multi_page_element != page.shared:
                raise ValidationError(
                    "This element type can't be added as root of a "
                    f"{'an unshared' if self.is_multi_page_element else 'the shared'} "
                    "page."
                )

    def after_create(self, instance: ElementSubClass, values: Dict):
        """
        This hook is called right after the element has been created.

        :param instance: The created element instance.
        :param values: The values that were passed when creating the field
            instance.
        """

    def after_update(
        self,
        instance: ElementSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ):
        """
        This hook is called right after the element has been updated.

        :param instance: The updated element instance.
        :param values: The values that were passed when updating the instance.
        :param changes: A dictionary containing all changes which were made to the
            element prior to `after_update` being called.
        """

    def before_delete(self, instance: ElementSubClass):
        """
        This hook is called just before the element will be deleted.

        :param instance: The to be deleted element instance.
        """

    def import_context_addition(self, instance: ElementSubClass) -> Dict[str, Any]:
        """
        This hook allow to specify extra context data when importing objects related
        to this one like child elements, collection fields or workflow actions.
        This extra context is then used as import context for these objects.

        :param instance: The instance we want the context for.
        :return: An object containing the extra context for the import process.
        """

        return {}

    def import_serialized(
        self,
        page: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: ZipFile | None = None,
        storage: Storage | None = None,
        cache: Dict[str, Any] | None = None,
        **kwargs,
    ) -> ElementSubClass:
        from baserow.contrib.builder.elements.handler import ElementHandler

        # Add mapping for builder element event uids (for collection field or other
        # elements that are using dynamic events.
        if "builder_element_event_uids" not in id_mapping:
            id_mapping["builder_element_event_uids"] = {}

        if cache is None:
            cache = {}

        import_context = {}

        parent_element_id = serialized_values["parent_element_id"]

        # If we have a parent element then we want to add used its import context
        if parent_element_id:
            imported_parent_element_id = id_mapping["builder_page_elements"][
                parent_element_id
            ]
            import_context = ElementHandler().get_import_context_addition(
                imported_parent_element_id,
                element_map=cache.get("imported_element_map", None),
            )

        existing_roles = cache.get("existing_roles", {}).get(page.builder.id)
        if not existing_roles:
            existing_roles = UserSourceHandler().get_all_roles_for_application(
                page.builder
            )
            cache.setdefault("existing_roles", {})[page.builder.id] = existing_roles

        serialized_values["roles"] = self.sanitize_element_roles(
            serialized_values.get("roles", []),
            existing_roles,
            id_mapping.get("user_sources", {}),
        )

        created_instance = super().import_serialized(
            page,
            serialized_values,
            id_mapping,
            files_zip,
            storage,
            cache,
            **(kwargs | import_context),
        )

        # Update formulas of the current element
        updated_models = self.import_formulas(
            created_instance, id_mapping, import_formula, **(kwargs | import_context)
        )

        [m.save() for m in updated_models]

        # Add created instance to an element cache
        cache.setdefault("imported_element_map", {})[
            created_instance.id
        ] = created_instance

        return created_instance

    def sanitize_element_roles(
        self,
        roles: List[str],
        existing_roles: List[str],
        user_sources_mapping: Dict[int, int],
    ) -> List[str]:
        """
        Given a list of roles, return a sanitized version of it. The sanitized
        version should not contain any invalid roles.

        An invalid role is a role name that doesn't exist (e.g. due to renaming
        or deletion). Also, Default User Roles are updated to ensure they contain
        the new User Source's ID.
        """

        sanitized_roles = []
        for role in roles:
            if role in existing_roles:
                sanitized_roles.append(role)
                continue

            # Ensure the default role is using the newly published UserSource ID
            prefix = str(DEFAULT_USER_ROLE_PREFIX)
            if role.startswith(prefix) and user_sources_mapping:
                old_user_source_id = int(role[len(prefix) :])
                # if the user source has been removed in the meantime we can't have
                # a match so we just ignore it.
                if old_user_source_id in user_sources_mapping:
                    new_user_source_id = user_sources_mapping[old_user_source_id]
                    new_role_name = f"{prefix}{new_user_source_id}"
                    if new_role_name in existing_roles:
                        sanitized_roles.append(new_role_name)

        return sanitized_roles

    def serialize_property(
        self,
        element: Element,
        prop_name: str,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "order":
            return str(element.order)

        if prop_name == "style_background_file_id":
            return UserFileHandler().export_user_file(
                element.style_background_file,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
            )

        return super().serialize_property(
            element, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
        **kwargs,
    ) -> Any:
        """
        This hooks allow to customize the deserialization of a property.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :param files_zip: the zip file containing the files.
        :param storage: the storage where the files should be stored.
        :param cache: a cache dict that can be used to store temporary data.
        :return: the deserialized version for this property.
        """

        if cache is None:
            cache = {}

        if prop_name == "parent_element_id":
            return id_mapping[BUILDER_PAGE_ELEMENTS].get(
                value,
                value,
            )

        if prop_name == "style_background_file_id":
            user_file = UserFileHandler().import_user_file(
                value, files_zip=files_zip, storage=storage
            )
            if user_file:
                return user_file.id
            return None

        # Compat with old exported JSONs
        # Can be removed in January 2025
        if prop_name == "style_background_mode":
            return value or "fill"

        # Compat with old exported JSONs
        # Can be removed in January 2025
        if prop_name in [
            "style_margin_bottom",
            "style_margin_top",
            "style_margin_left",
            "style_margin_right",
        ]:
            return value or 0

        return value

    @abstractmethod
    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        """
        Returns a sample of params for this type. This can be used to tests the element
        for instance.

        :param pytest_data_fixture: A Pytest data fixture which can be used to
            create related objects when the import / export functionality is tested.
        """

    def formula_generator(
        self, element: Element
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that returns formula fields for the LinkElementType.

        Unlike other Element types, this one has its formula fields in the
        page_parameters and query_prameters JSON fields.
        """

        yield from super().formula_generator(element)

        # Deal with visibility_condition
        new_formula = yield element.visibility_condition
        if new_formula is not None:
            element.visibility_condition = new_formula
            yield element


ElementTypeSubClass = TypeVar("ElementTypeSubClass", bound=ElementType)


class ElementTypeRegistry(
    Registry[ElementTypeSubClass],
    ModelRegistryMixin[ElementSubClass, ElementTypeSubClass],
    CustomFieldsRegistryMixin,
):
    """
    Contains all registered element types.
    """

    name = "element_type"


element_type_registry = ElementTypeRegistry()


class CollectionFieldType(
    BuilderInstanceWithFormulaMixin,
    CustomFieldsInstanceMixin,
    Instance,
    ABC,
):
    """Collection element field type"""

    SerializedDict: TypedDict

    model_class = CollectionField

    def serialize_property(self, config: Dict[str, Any], prop_name: str):
        return config[prop_name]

    def export_serialized(self, instance: CollectionField) -> Dict[str, Any]:
        property_names = self.SerializedDict.__annotations__.keys()

        serialized_config = self.SerializedDict(
            **{
                key: self.serialize_property(instance.config, key)
                for key in property_names
                if key in instance.config
            }
        )

        serialized = {
            "uid": str(instance.uid),
            "name": instance.name,
            "type": instance.type,
            "styles": instance.styles,
            "config": serialized_config,
        }

        return serialized

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        serialized_values: Dict[str, Any],
        **kwargs,
    ) -> Any:
        """
        This hooks allow to customize the deserialization of a property.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :param serialized_values: the serialized values, which can be accessed
            during deserialization to perform extra checks.
        :return: the deserialized version for this property.
        """

        return value

    def create_instance_from_serialized(
        self, serialized_values: Dict[str, Any]
    ) -> CollectionField:
        """
        Create the instance related to the given serialized values.
        Allow to hook into instance creation while still having the serialized values.

        :param serialized_values: the deserialized values.
        :return: the created instance.
        """

        # We don't save the new instance intentionally to be able to bulk create them
        return CollectionField(**serialized_values)

    def import_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Any],
        **kwargs,
    ) -> CollectionField:
        """
        Imports the previously exported dict generated by the `export_serialized`
        method.

        An id_mapping for this class is populated during the process.

        :param serialized_values: The dict containing the serialized values.
        :param id_mapping: Used to mapped object ids from export to newly
            created instances.
        :return: The created instance.
        """

        deserialized_config = {}
        for name in self.SerializedDict.__annotations__.keys():
            # If any field declared in the `SerializedDict` is not present in
            # `serialized_values`, try to use a default value instead.
            # The default value is retrieved from the `serialized_field_overrides`
            # method, if present.
            serializer_field_override = self.serializer_field_overrides.get(name)
            default = getattr(serializer_field_override, "default", None)
            deserialized_config[name] = self.deserialize_property(
                name,
                serialized_values["config"].get(name, default),
                id_mapping,
                serialized_values,
                **kwargs,
            )

        # Generate a new `uid` for this collection field.
        deserialized_uid = str(uuid.uuid4())

        if "uid" in serialized_values:
            # Map the old uid to the new uid. This ensures that any workflow
            # actions with an `event` pointing to the old uid will have the
            # pointer to the new uid.
            id_mapping["builder_element_event_uids"][
                serialized_values["uid"]
            ] = deserialized_uid

        deserialized_values = {
            "uid": deserialized_uid,
            "config": deserialized_config,
            "type": serialized_values["type"],
            "styles": serialized_values.get("styles", {}),
            "name": serialized_values["name"],
        }

        return self.create_instance_from_serialized(deserialized_values)

    def get_serializer(
        self,
        model_instance_or_instances: Union[models.Model, List[models.Model]],
        base_class: Optional[serializers.ModelSerializer] = None,
        context: Optional[Dict[str, Any]] = None,
        request: bool = False,
        **kwargs: Dict[str, Any],
    ) -> serializers.ModelSerializer:
        """
        Returns an instantiated model serializer based on this type field names and
        overrides. The provided model instance will be used instantiate the serializer.

        :param model_instance_or_instances: The instance or a list of instances for
            which the serializer must be generated.
        :param base_class: The base serializer class that must be extended. For example
            common fields could be stored here.
        :param context: Extra context arguments to pass to the serializers context.
        :param request: True if you want the request serializer.
        :param kwargs: The kwargs are used to initialize the serializer class.
        :return: The instantiated generated model serializer.
        """

        if context is None:
            context = {}

        model_instance_or_instances = model_instance_or_instances

        serializer_class = self.get_serializer_class(
            base_class=base_class, request_serializer=request
        )

        return serializer_class(model_instance_or_instances, context=context, **kwargs)

    def before_delete(self, instance: CollectionField):
        """
        This hooks is called before we delete a collection field and gives the
        opportunity to clean up things.
        """

    def formula_generator(
        self, collection_field: CollectionField
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that iterates over formula fields for CollectionField.

        Some formula fields are in the config JSON field, e.g. page_parameters.
        """

        for formula_field in self.simple_formula_fields:
            formula = collection_field.config.get(formula_field, "")
            new_formula = yield BaserowFormulaObject.to_formula(formula)
            if new_formula is not None:
                collection_field.config[formula_field] = new_formula
                yield collection_field


CollectionFieldTypeSubClass = TypeVar(
    "CollectionFieldTypeSubClass", bound=CollectionFieldType
)


class CollectionFieldTypeRegistry(
    Registry[CollectionFieldTypeSubClass],
    CustomFieldsRegistryMixin,
):
    """
    Contains all registered collection field types.
    """

    name = "collection_field_type"


collection_field_type_registry = CollectionFieldTypeRegistry()
