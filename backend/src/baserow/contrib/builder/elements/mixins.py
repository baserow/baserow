from typing import Any, Dict, List, Optional, Tuple, Type
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.api.elements.serializers import (
    CollectionElementPropertyOptionsSerializer,
    CollectionFieldSerializer,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.exceptions import (
    CollectionElementPropertyOptionsNotUnique,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import (
    CollectionElement,
    CollectionElementPropertyOptions,
    CollectionField,
    ContainerElement,
    Element,
    FormElement,
)
from baserow.contrib.builder.elements.registries import (
    collection_field_type_registry,
    element_type_registry,
)
from baserow.contrib.builder.elements.signals import elements_moved
from baserow.contrib.builder.elements.types import (
    CollectionElementSubClass,
    ElementSubClass,
)
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.types import ElementDict
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.registries import service_type_registry
from baserow.core.utils import merge_dicts_no_duplicates


class ContainerElementTypeMixin:
    # Container element types are imported first.
    import_element_priority = 2

    class SerializedDict(ElementDict):
        pass

    @property
    def child_types_allowed(self) -> List[str]:
        """
        Lets you define which children types can be placed inside the container.

        By default, multi-page elements are not allowed inside any container.
        """

        return [
            element_type
            for element_type in element_type_registry.get_all()
            if not element_type.is_multi_page_element
        ]

    def get_new_place_in_container(
        self, container_element: ContainerElement, places_removed: List[str]
    ) -> Optional[str]:
        """
        Provides an alternative place that elements can move to when places in the
        container are removed.

        :param container_element: The container element that has places removed
        :param places_removed: The places that are being removed
        :return: The new place in the container the elements can be moved to
        """

        return None

    def get_places_in_container_removed(
        self, values: Dict, instance: ContainerElement
    ) -> List[str]:
        """
        This method defines what elements in the container have been removed preceding
        an update of hte container element.

        :param values: The new values that are being set
        :param instance: The current state of the element
        :return: The places in the container that have been removed
        """

        return []

    def apply_order_by_children(self, queryset: QuerySet[Element]) -> QuerySet[Element]:
        """
        Defines the order of the children inside the container.

        :param queryset: The queryset that the order is applied to.
        :return: A queryset with the order applied to
        """

        return queryset.order_by("place_in_container", "order")

    def prepare_value_for_db(
        self, values: Dict, instance: Optional[ContainerElement] = None
    ):
        if instance is not None:  # This is an update operation
            places_removed = self.get_places_in_container_removed(values, instance)

            if len(places_removed) > 0:
                instances_moved = ElementHandler().before_places_in_container_removed(
                    instance, places_removed
                )

                elements_moved.send(self, page=instance.page, elements=instances_moved)

        return super().prepare_value_for_db(values, instance)

    def validate_place_in_container(
        self, place_in_container: str, instance: ContainerElement
    ):
        """
        Validate that the place in container being set on a child is valid.

        :param place_in_container: The place in container being set
        :param instance: The instance of the container element
        :raises DRFValidationError: If the place in container is invalid
        """

        return True


class CollectionElementTypeMixin:
    is_collection_element = True

    # Three properties which define whether this collection element
    # is allowed to be publicly sortable, filterable and searchable
    # by page visitors. Can be overridden by subclasses to influence
    # whether page designers can flag collection elements and their
    # properties as sortable, filterable and searchable.
    is_publicly_sortable = True
    is_publicly_filterable = True
    is_publicly_searchable = True

    simple_formula_fields = ["button_load_more_label"]

    allowed_fields = [
        "data_source",
        "data_source_id",
        "items_per_page",
        "schema_property",
        "button_load_more_label",
    ]
    serializer_field_names = [
        "schema_property",
        "data_source_id",
        "items_per_page",
        "button_load_more_label",
        "property_options",
        "is_publicly_sortable",
        "is_publicly_filterable",
        "is_publicly_searchable",
    ]

    class SerializedDict(ElementDict):
        data_source_id: int
        items_per_page: int
        button_load_more_label: str
        schema_property: str
        property_options: List[Dict]

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).prefetch_related("property_options")

    def after_update(
        self, instance: CollectionElementSubClass, values, changes: Dict[str, Tuple]
    ):
        """
        After the element has been updated we need to update the property options.

        :param instance: The instance of the element that has been updated.
        :param values: The values that have been updated.
        :param changes: A dictionary containing all changes which were made to the
            collection element prior to `after_update` being called.
        :return: None
        """

        # Following a DataSource change, from one DataSource to another, we drop all
        # property options. This is due to the fact that the `schema_property` in the
        # property options are specific to that data source's schema.
        data_source_changed = "data_source" in changes

        if "property_options" in values or data_source_changed:
            instance.property_options.all().delete()
            try:
                CollectionElementPropertyOptions.objects.bulk_create(
                    [
                        CollectionElementPropertyOptions(
                            **option,
                            element=instance,
                        )
                        for option in values.get("property_options", [])
                    ]
                )
            except IntegrityError as e:
                if "unique constraint" in e.args[0]:
                    raise CollectionElementPropertyOptionsNotUnique()
                raise e

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "is_publicly_sortable": serializers.BooleanField(
                read_only=True,
                default=self.is_publicly_sortable,
                help_text="Whether this collection element is publicly sortable.",
            ),
            "is_publicly_filterable": serializers.BooleanField(
                read_only=True,
                default=self.is_publicly_filterable,
                help_text="Whether this collection element is publicly filterable.",
            ),
            "is_publicly_searchable": serializers.BooleanField(
                read_only=True,
                default=self.is_publicly_searchable,
                help_text="Whether this collection element is publicly searchable.",
            ),
            "data_source_id": serializers.IntegerField(
                allow_null=True,
                default=None,
                help_text=CollectionElement._meta.get_field("data_source").help_text,
                required=False,
            ),
            "schema_property": serializers.CharField(
                allow_null=True,
                default=None,
                help_text=CollectionElement._meta.get_field(
                    "schema_property"
                ).help_text,
                required=False,
            ),
            "items_per_page": serializers.IntegerField(
                default=20,
                help_text=CollectionElement._meta.get_field("items_per_page").help_text,
                min_value=0,
                required=False,
            ),
            "button_load_more_label": FormulaSerializerField(
                help_text=CollectionElement._meta.get_field(
                    "button_load_more_label"
                ).help_text,
                required=False,
            ),
            "property_options": CollectionElementPropertyOptionsSerializer(
                many=True,
                required=False,
                help_text="The schema property options that can be set for the collection element.",
            ),
        }

    def prepare_value_for_db(
        self, values: Dict, instance: Optional[CollectionElementSubClass] = None
    ):
        if "data_source_id" in values:
            data_source_id = values.pop("data_source_id")
            if data_source_id is not None:
                schema_property = values.get("schema_property", None)
                data_source = DataSourceHandler().get_data_source(data_source_id)
                if data_source.service:
                    service_type = data_source.service.specific.get_type()
                    if service_type.returns_list and schema_property:
                        raise DRFValidationError(
                            "Data sources which return multiple rows cannot be "
                            "used in conjunction with the schema property."
                        )
                else:
                    raise DRFValidationError(
                        f"Data source {data_source_id} is partially "
                        "configured and not ready for use."
                    )

                if instance:
                    element_page = instance.page
                else:
                    element_page = values["page"]

                # The data source must belong to the same element page or the shared
                # page.
                if data_source.page_id not in [
                    element_page.id,
                    element_page.builder.shared_page.id,
                ]:
                    raise RequestBodyValidationException(
                        {
                            "data_source_id": [
                                {
                                    "detail": "The provided data source is not "
                                    "available for this element.",
                                    "code": "invalid_data_source",
                                }
                            ]
                        }
                    )
                values["data_source"] = data_source
            else:
                values["data_source"] = None

        if "items_per_page" in values:
            data_source = values.get(
                "data_source", instance.data_source if instance else None
            )

            if (
                data_source
                and data_source.service
                and data_source.service.get_type().returns_list
            ):
                max_count = data_source.service.get_type().get_max_result_limit(
                    data_source.service.specific
                )
            else:
                max_count = 20

            if values["items_per_page"] > max_count:
                raise RequestBodyValidationException(
                    {
                        "items_per_page": [
                            {
                                "detail": f"Maximum allowed value is {max_count}",
                                "code": "invalid_value",
                            }
                        ]
                    }
                )

        return super().prepare_value_for_db(values, instance)

    def serialize_property(
        self,
        element: CollectionElementSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "property_options":
            return [
                {
                    "schema_property": po.schema_property,
                    "filterable": po.filterable,
                    "sortable": po.sortable,
                    "searchable": po.searchable,
                }
                for po in element.property_options.all()
            ]

        return super().serialize_property(
            element,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
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
        if prop_name == "data_source_id" and value:
            return id_mapping["builder_data_sources"][value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def import_context_addition(self, instance: CollectionElement) -> Dict[str, int]:
        """
        Given a collection element, adds the `data_source_id` and `schema_property`
        to the import context.

        The data_source_id is not store in some formulas (current_record ones) so
        we need the generate this import context for all formulas of this element.
        """

        # If `instance` isn't a `CollectionElement`, it'll be because we just tried
        # to get the `import_context_addition` of a collection element, but it's a
        # child of a container. If that happens, just return a blank dict.
        instance = instance.specific
        if not isinstance(instance, CollectionElement):
            return {}

        # Fetch the parent element's import context, as we need to ensure
        # that if `instance` doesn't have a `data_source_id`, we can fall back
        # to the parent element's `data_source_id` instead.
        parent_results = (
            self.import_context_addition(instance.parent_element)
            if instance.parent_element_id
            else {}
        )

        results = {
            "data_source_id": instance.data_source_id
            or parent_results.get("data_source_id")
        }

        if instance.schema_property is not None:
            results["schema_property"] = instance.schema_property

        return results

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> CollectionElementSubClass:
        """
        Responsible for creating the property options from the serialized values.

        :param serialized_values: The serialized values of the element.
        :param id_mapping: A dictionary containing the mapping of the old and new ids.
        :param files_zip: The zip file containing the files that can be used.
        :param storage: The storage that can be used to store files.
        :param cache: A dictionary that can be used to cache data.
        :param kwargs: Additional keyword arguments.
        :return: The created instance.
        """

        property_options_values = serialized_values.pop("property_options", [])

        instance = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        service = None
        import_context = ElementHandler().get_import_context_addition(instance.id)
        if import_context["data_source_id"]:
            data_source = DataSourceHandler().get_data_source(
                import_context["data_source_id"]
            )
            service = data_source.service.specific

        # If we have a data source set, we'll find out what its service type is, and
        # use it to map the `schema_property` and `property_options` value `field_id`
        # to the new ID.
        service_type = service_type_registry.get_by_model(service) if service else None

        if service_type:
            # Use the service type to convert the `schema_property`
            # value if it's present in the ID mapping.
            if instance.schema_property:
                imported_schema_property = service_type.import_property_name(
                    instance.schema_property, id_mapping
                )
                if instance.schema_property != imported_schema_property:
                    instance.schema_property = imported_schema_property
                    instance.save(update_fields=["schema_property"])

            # Use the service type to convert the `property_options` list's
            # `schema_property` value if they're present in the ID mapping.
            property_options = []
            for po in property_options_values:
                imported_field_dbname = service_type.import_property_name(
                    po["schema_property"], id_mapping
                )
                # Trashed fields won't be included in the deserialized
                # property options, we'll skip it altogether.
                if imported_field_dbname is not None:
                    property_options.append(
                        {**po, "schema_property": imported_field_dbname}
                    )

            # Create property options
            options = [
                CollectionElementPropertyOptions(**po, element=instance)
                for po in property_options
            ]
            CollectionElementPropertyOptions.objects.bulk_create(options)
            instance.property_options.add(*options)

        return instance

    def extract_properties(self, instance: Element, **kwargs) -> Dict[int, List[str]]:
        """
        Some collection elements (e.g. Repeat Element) may have a nested
        collection element which uses a schema_property. This property points
        to a field name that is connected to the parent collection element's
        data source.

        This method is overridden to ensure that any schema_property is also
        included in the list of field names used by the element.
        """

        properties = super().extract_properties(instance, **kwargs)

        # if we have a data_source_id in the context from a parent or from the
        # current instance
        data_source_id = instance.data_source_id or kwargs.get("data_source_id", None)
        data_source = (
            DataSourceHandler().get_data_source(data_source_id, with_cache=True)
            if data_source_id
            else None
        )

        if (schema_property := instance.schema_property) and data_source:
            properties[data_source.service_id] = [schema_property]

        property_options = [
            field_name
            for field_name, options in ElementHandler()
            .get_element_property_options(instance)
            .items()
            if any(options.values())
        ]

        if data_source and property_options:
            properties.setdefault(data_source.service_id, []).extend(property_options)

        # We need the id for the element
        if data_source and data_source.service_id:
            service = data_source.service.specific
            id_property = service.get_type().get_id_property(service)
            if id_property not in properties.setdefault(service.id, []):
                properties[service.id].append(id_property)

        return properties


class CollectionElementWithFieldsTypeMixin(CollectionElementTypeMixin):
    """
    As subclass of `CollectionElementTypeMixin` which extends its functionality to
    include fields. This mixin is used for elements that have fields, like tables.
    """

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + ["fields"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            "fields": CollectionFieldSerializer(many=True, required=False),
        }

    class SerializedDict(CollectionElementTypeMixin.SerializedDict):
        fields: List[Dict]

    def serialize_property(
        self,
        element: CollectionElementSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "fields":
            return [
                collection_field_type_registry.get(f.type).export_serialized(f)
                for f in element.fields.all()
            ]

        return super().serialize_property(
            element,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def after_create(self, instance: CollectionElementSubClass, values):
        default_fields = [
            {
                "name": _("Column %(count)s") % {"count": 1},
                "type": "text",
                "config": {"value": ""},
            },
            {
                "name": _("Column %(count)s") % {"count": 2},
                "type": "text",
                "config": {"value": ""},
            },
            {
                "name": _("Column %(count)s") % {"count": 3},
                "type": "text",
                "config": {"value": ""},
            },
        ]

        fields = values.get("fields", default_fields)

        created_fields = CollectionField.objects.bulk_create(
            [
                CollectionField(**field, order=index)
                for index, field in enumerate(fields)
            ]
        )
        instance.fields.add(*created_fields)

    def after_update(
        self, instance: CollectionElementSubClass, values, changes: Dict[str, Tuple]
    ):
        """
        After the element has been updated we need to update the fields.

        :param instance: The instance of the element that has been updated.
        :param values: The values that have been updated.
        :param changes: A dictionary containing all changes which were made to the
            collection element prior to `after_update` being called.
        :return: None
        """

        if "fields" in values:
            # If the collection element contains fields that are being deleted,
            # we also need to delete the associated workflow actions.
            query = Q()
            for field in values["fields"]:
                if "uid" in field:
                    query |= Q(uid=field["uid"])

            # Call before delete hook of removed fields
            for field in instance.fields.exclude(query):
                field.get_type().before_delete(field)

            # Remove previous fields
            instance.fields.all().delete()

            created_fields = CollectionField.objects.bulk_create(
                [
                    CollectionField(**field, order=index)
                    for index, field in enumerate(values["fields"])
                ]
            )
            instance.fields.add(*created_fields)

        super().after_update(instance, values, changes)

    def before_delete(self, instance: CollectionElementSubClass):
        # Call the before_delete hook of all fields
        for field in instance.fields.all():
            field.get_type().before_delete(field)

        instance.fields.all().delete()

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """Deals with the fields"""

        fields = serialized_values.pop("fields", [])

        instance = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        import_field_context = ElementHandler().get_import_context_addition(
            instance.id, cache.get("imported_element_map")
        )

        fields = [
            collection_field_type_registry.get(f["type"]).import_serialized(
                f, id_mapping, **(kwargs | import_field_context)
            )
            for f in fields
        ]

        # Add the field order
        for i, f in enumerate(fields):
            f.order = i

        # Create fields
        created_fields = CollectionField.objects.bulk_create(fields)

        instance.fields.add(*created_fields)

        return instance

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
        """
        This method is overridden to ensure that the import_context contains
        the data sources and correctly imports formulas.
        """

        # Import the element itself
        created_instance = super().import_serialized(
            page,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # For collection fields, import_context should include the current element
        import_context = ElementHandler().get_import_context_addition(
            created_instance.id,
            element_map=cache.get("imported_element_map", None) if cache else None,
        )

        # Import the collection field formulas
        updated_models = []
        for collection_field in created_instance.fields.all():
            collection_field.get_type().import_formulas(
                collection_field,
                id_mapping,
                import_formula,
                **(kwargs | import_context),
            )
            updated_models.append(collection_field)

        [m.save() for m in updated_models]

        return created_instance

    def extract_properties(
        self,
        instance: CollectionElementSubClass,
        **kwargs,
    ) -> Dict[int, List[str]]:
        """
        Extract all formula field names of the collection element instance.

        Returns a dict where keys are the Service ID and values are a list of
        field names, e.g.: {164: ['field_5440', 'field_5441', 'field_5439']}
        """

        # First get from the current element
        result = super().extract_properties(instance, **kwargs)

        # then extract the properties used in the collection field formulas
        formula_context = kwargs | self.import_context_addition(instance)

        for collection_field in instance.fields.all():
            result = merge_dicts_no_duplicates(
                result,
                collection_field.get_type().extract_properties(
                    collection_field, **formula_context
                ),
            )

        return result


class FormElementTypeMixin:
    # Form element types are imported second, after containers.
    import_element_priority = 1

    def is_valid(
        self,
        element: Type[FormElement],
        value: Any,
        dispatch_context: DispatchContext,
    ) -> bool:
        """
        Given an element and form data value, returns whether it's valid.
        Used by `FormDataProviderType` to determine if form data is valid.

        :param element: The element we're trying to use form data in.
        :param value: The form data value, which may be invalid.
        :param dispatch_context: The dispatch context of the request.
        :return: Whether the value is valid or not for this element.
        """

        if element.required and not value:
            raise ValueError("The value is required")

        return value


class MultiPageElementTypeMixin:
    is_multi_page_element = True

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + [
            "share_type",
            "pages",
        ]

    @property
    def allowed_fields(self):
        return super().allowed_fields + [
            "share_type",
        ]

    class SerializedDict(ElementDict):
        share_type: str
        pages: List[int]

    def after_create(self, instance, values):
        """
        Add the pages
        """

        from baserow.contrib.builder.pages.models import Page

        super().after_create(instance, values)

        if "pages" in values:
            pages = PageHandler().get_pages(
                instance.page.builder,
                base_queryset=Page.objects_without_shared.filter(
                    id__in=[p.id for p in values["pages"]]
                ),
            )
            instance.pages.add(*pages)

    def after_update(self, instance: Any, values: Dict, changes: Dict[str, Tuple]):
        """
        Updates the pages.
        """

        from baserow.contrib.builder.pages.models import Page

        super().after_update(instance, values, changes)

        if "pages" in values:
            pages = PageHandler().get_pages(
                instance.page.builder,
                base_queryset=Page.objects_without_shared.filter(
                    id__in=[p.id for p in values["pages"]]
                ),
            )
            instance.pages.clear()
            instance.pages.add(*pages)

    def serialize_property(
        self,
        element: "MultiPageElementTypeMixin",
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "pages":
            return [page.id for page in element.pages.all()]

        return super().serialize_property(
            element,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """Deals with the fields"""

        pages = serialized_values.pop("pages", [])

        instance = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        pages = [id_mapping["builder_pages"][page_id] for page_id in pages]

        if pages:
            instance.pages.add(*pages)

        return instance

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {"share_type": "all"}
