from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import FieldDoesNotExist as DjangoFieldDoesNotExist
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from baserow.contrib.builder.data_providers.exceptions import (
    DataProviderChunkInvalidException,
)
from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.api.utils import extract_field_ids_from_list
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    IncompatibleField,
)
from baserow.contrib.database.fields.field_types import (
    CreatedByFieldType,
    LastModifiedByFieldType,
    LinkRowFieldType,
    MultipleCollaboratorsFieldType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import (
    field_aggregation_registry,
    field_type_registry,
)
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.exceptions import (
    CannotCreateRowsInTable,
    CannotDeleteRowsInTable,
    RowDoesNotExist,
)
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.table.service import TableService
from baserow.contrib.database.views.exceptions import (
    AggregationTypeDoesNotExist,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.service import ViewService
from baserow.contrib.integrations.local_baserow.api.serializers import (
    LocalBaserowTableServiceFieldMappingSerializer,
)
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSearchableMixin,
    LocalBaserowTableServiceSortableMixin,
    LocalBaserowTableServiceSpecificRowMixin,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowDeleteRow,
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowTableService,
    LocalBaserowTableServiceFieldMapping,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
    LocalBaserowUpsertRow,
)
from baserow.contrib.integrations.local_baserow.utils import (
    guess_cast_function_from_response_serializer_field,
    guess_json_type_from_response_serializer_field,
)
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.handler import CoreHandler
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import DoesNotExist, ServiceImproperlyConfigured
from baserow.core.services.registries import (
    DispatchTypes,
    ListServiceTypeMixin,
    ServiceType,
)
from baserow.core.services.types import (
    ServiceDict,
    ServiceFilterDictSubClass,
    ServiceSortDictSubClass,
    ServiceSubClass,
)
from baserow.core.utils import atomic_if_not_already

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel, Table


class LocalBaserowServiceType(ServiceType):
    """
    The `ServiceType` for all `LocalBaserow` integration services.
    """

    def get_schema_for_return_type(
        self, service: ServiceSubClass, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Responsible for returning the JSON Schema object based on the
        `returns_list` attribute set on this service type.

        :param service: The service we are generating a schema for.
        :param properties: A dictionary of properties which describe this service.
        :return: A JSON Schema formatted dictionary.
        """

        if self.returns_list:
            return {
                "items": {"type": "object", "properties": properties},
                "title": self.get_schema_name(service),
                "type": "array",
            }
        else:
            return {
                "properties": properties,
                "title": self.get_schema_name(service),
                "type": "object",
            }


class LocalBaserowTableServiceType(LocalBaserowServiceType):
    """
    The `ServiceType` for `LocalBaserowTableService` subclasses.
    """

    allowed_fields = ["table", "integration"]
    serializer_field_names = ["table_id", "integration_id"]
    serializer_field_overrides = {
        "table_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the Baserow table we want the data for.",
        ),
        "integration_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the Baserow integration we want the data for.",
        ),
    }

    # Three lists which represent the Baserow `FieldType` which are not permitted
    # as sortable, searchable and filterable in our integrations. These field types
    # may well be sortable, searchable and filterable normally, but not in integrations.
    unsupported_adhoc_sortable_field_types = []
    unsupported_adhoc_searchable_field_types = []
    unsupported_adhoc_filterable_field_types = [
        LinkRowFieldType.type,
        CreatedByFieldType.type,
        LastModifiedByFieldType.type,
        MultipleCollaboratorsFieldType.type,
    ]

    class SerializedDict(ServiceDict):
        table_id: int

    def build_queryset(
        self,
        service: LocalBaserowTableService,
        table: "Table",
        dispatch_context: DispatchContext,
        model: Optional[Type["GeneratedTableModel"]] = None,
    ) -> QuerySet:
        """
        Build the queryset for this table, checking for the appropriate permissions.
        """

        integration = service.integration.specific

        CoreHandler().check_permissions(
            integration.authorized_user,
            ListRowsDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        if not model:
            model = self.get_table_model(service)

        queryset = self.get_queryset(service, table, dispatch_context, model)

        return queryset

    def get_queryset(
        self,
        service: ServiceSubClass,
        table: "Table",
        dispatch_context: DispatchContext,
        model: Type["GeneratedTableModel"],
    ):
        """Return the queryset for this model."""

        only_field_names = self.get_used_field_names(service, dispatch_context)

        return model.objects.all().enhance_by_fields(
            only_field_ids=extract_field_ids_from_list(only_field_names)
        )

    def enhance_queryset(self, queryset):
        return queryset.select_related(
            "table__database__workspace",
        ).prefetch_related("table__field_set")

    def resolve_service_formulas(
        self,
        service: ServiceSubClass,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        A hook called before the `LocalBaserowTableServiceType` subclass dispatch
        calls. It ensures we check the service has a `Table` before execution.

        :param service: A `LocalBaserowTableService` instance.
        :param dispatch_context: The dispatch_context instance used to
            resolve formulas (if any).
        :raises ServiceImproperlyConfigured: When we try and dispatch a service that
            has no `Table` associated with it, or if the table/database is trashed.
        """

        if service.table_id is None:
            raise ServiceImproperlyConfigured("The table property is missing.")

        try:
            table = TableHandler().get_table(service.table_id)
        except TableDoesNotExist as e:
            raise ServiceImproperlyConfigured("The specified table is trashed") from e

        resolved_values = super().resolve_service_formulas(service, dispatch_context)
        resolved_values["table"] = table

        return resolved_values

    def import_property_name(
        self, property_name: Union[str, int], id_mapping: Dict[str, Any]
    ) -> Optional[str]:
        """
        Responsible for taking a Local Baserow property name (`Field.db_column`),
        using the ID mapping, amd extracting its mapped ID in a new workspace. If the
        field ID isn't present in the mapping, then the field was never serialized as
        it was deleted.

        :param property_name: The property name we want to import.
        :param id_mapping: The ID mapping dictionary.
        :return: The new property name, or None if the field was deleted.
        """

        if (
            property_name
            and "database_fields" in id_mapping
            and property_name.startswith("field_")
        ):
            field_id = get_field_id_from_field_key(property_name)
            new_field_id = id_mapping["database_fields"].get(field_id)
            return f"field_{new_field_id}" if new_field_id else None
        return property_name

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Get the table and field IDs from the mapping if they exist.
        """

        if prop_name == "table_id" and "database_tables" in id_mapping:
            return id_mapping["database_tables"].get(value, None)

        if "database_fields" in id_mapping and prop_name in ["filters", "sortings"]:
            return [
                {
                    **item,
                    "field_id": id_mapping["database_fields"][item["field_id"]],
                }
                for item in value
            ]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> ServiceSubClass:
        """
        Responsible for creating the `filters` and `sortings`.

        :param serialized_values: The serialized values we'll use to import.
        :param id_mapping: The id_mapping dictionary.
        :return: A Service.
        """

        filters = serialized_values.pop("filters", [])
        sortings = serialized_values.pop("sortings", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # Create filters
        LocalBaserowTableServiceFilter.objects.bulk_create(
            [
                LocalBaserowTableServiceFilter(
                    **service_filter,
                    order=index,
                    service=service,
                )
                for index, service_filter in enumerate(filters)
            ]
        )

        # Create sortings
        LocalBaserowTableServiceSort.objects.bulk_create(
            [
                LocalBaserowTableServiceSort(
                    **service_sorting,
                    order=index,
                    service=service,
                )
                for index, service_sorting in enumerate(sortings)
            ]
        )

        return service

    def update_service_sortings(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_sorts: Optional[List[ServiceSortDictSubClass]] = None,
    ):
        with atomic_if_not_already():
            service.service_sorts.all().delete()
            LocalBaserowTableServiceSort.objects.bulk_create(
                [
                    LocalBaserowTableServiceSort(
                        **service_sort, service=service, order=index
                    )
                    for index, service_sort in enumerate(service_sorts)
                ]
            )

    def update_service_filters(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_filters: Optional[List[ServiceFilterDictSubClass]] = None,
    ):
        with atomic_if_not_already():
            service.service_filters.all().delete()
            LocalBaserowTableServiceFilter.objects.bulk_create(
                [
                    LocalBaserowTableServiceFilter(
                        **service_filter, service=service, order=index
                    )
                    for index, service_filter in enumerate(service_filters)
                ]
            )

    def after_update(
        self,
        instance: ServiceSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ) -> None:
        """
        Responsible for updating service filters and sorts which have been
        PATCHED to the data source / service endpoint. At the moment we
        destroy all current filters and sorts, and create the ones present
        in `service_filters` / `service_sorts` respectively.

        :param instance: The service we want to manage filters/sorts for.
        :param values: A dictionary which may contain filters/sorts.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        # Following a Table change, from one Table to another, we drop all filters
        # and sorts. This is due to the fact that both point at specific table fields.
        from_table, to_table = changes.get("table", (None, None))
        if from_table and to_table:
            instance.service_filters.all().delete()
            instance.service_sorts.all().delete()
        else:
            if "service_filters" in values:
                self.update_service_filters(instance, values["service_filters"])
            if "service_sorts" in values:
                self.update_service_sortings(instance, values["service_sorts"])

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[ServiceSubClass] = None,
    ) -> Dict[str, Any]:
        """Load the table instance instead of the ID."""

        # Check if we already have a table. We may have already
        # added it in `LocalBaserowViewServiceType.prepare_values`.
        if "table_id" in values and "table" not in values:
            table_id = values.pop("table_id")
            if table_id is not None:
                try:
                    table = TableService().get_table(user, table_id)
                except TableDoesNotExist:
                    raise DRFValidationError(
                        f"The table with ID {table_id} does not exist."
                    )
                values["table"] = table
            else:
                values["table"] = None

        return super().prepare_values(values, user, instance)

    def generate_schema(self, service: ServiceSubClass) -> Optional[Dict[str, Any]]:
        """
        Responsible for generating a dictionary in the JSON Schema spec. This helps
        inform the frontend data source form and data explorer about the type of
        schema the service is interacting with.

        :param service: A `LocalBaserowTableService` subclass.
        :return: A schema dictionary, or None if no `Table` has been applied.
        """

        table = service.table
        if not table:
            return None

        properties = {
            "id": {
                "type": "number",
                "title": "Id",
                "sortable": False,
                "filterable": False,
                "searchable": False,
            }
        }
        for field_object in self.get_table_field_objects(service):
            field_type = field_object["type"]
            field = field_object["field"]
            # Only `TextField` has a default value at the moment.
            default_value = getattr(field, "text_default", None)
            field_serializer = field_type.get_serializer(field, FieldSerializer)
            properties[field.db_column] = {
                "title": field.name,
                "default": default_value,
                "searchable": field_type.is_searchable(field)
                and field_type.type
                not in self.unsupported_adhoc_searchable_field_types,
                "sortable": field_type.check_can_order_by(field)
                and field_type.type not in self.unsupported_adhoc_sortable_field_types,
                "filterable": field_type.check_can_filter_by(field)
                and field_type.type
                not in self.unsupported_adhoc_filterable_field_types,
                "original_type": field_type.type,
                "metadata": field_serializer.data,
            } | self.get_json_type_from_response_serializer_field(field, field_type)

        return self.get_schema_for_return_type(service, properties)

    def get_schema_name(self, service: ServiceSubClass) -> str:
        """
        The default `LocalBaserowTableService` schema name.

        :param service: The service we want to generate a schema `title` with.
        :return: A string.
        """

        return f"Table{service.table_id}Schema"

    def get_used_field_names(
        self, service: LocalBaserowTableService, dispatch_context: DispatchContext
    ) -> Optional[List[str]]:
        """
        Retrieves the list of used field for this dispatch_context.

        :param service: The service used for the dispatch.
        :param dispatch_context: The context object.

        Returns: A list of field names associated with the service ID if available,
          otherwise None.
        """

        if isinstance(dispatch_context.public_formula_fields, dict):
            all_field_names = dispatch_context.public_formula_fields.get("all", {}).get(
                service.id, None
            )
            if all_field_names is not None:
                return all_field_names

        return None

    def get_table_model(
        self, service: LocalBaserowTableService
    ) -> Optional["GeneratedTableModel"]:
        """
        Returns the model for the table associated with the given service.
        """

        if getattr(service, "_table_model", None) is None:
            table = service.table

            if not table:
                return None

            setattr(service, "_table_model", table.get_model())

        return getattr(service, "_table_model")

    def get_table_field_objects(self, service: LocalBaserowTableService) -> List[Dict]:
        """
        Returns the fields of the table associated with the given service.
        """

        model = self.get_table_model(service)

        if model is None:
            return []

        return model.get_field_objects()

    def get_context_data(self, service: ServiceSubClass) -> Optional[Dict[str, Any]]:
        table = service.table
        if not table:
            return None

        ret = {}
        for field_object in self.get_table_field_objects(service):
            field_type = field_object["type"]
            if field_type.can_have_select_options:
                field_serializer = field_type.get_serializer(
                    field_object["field"], FieldSerializer
                )
                ret[field_object["name"]] = field_serializer.data["select_options"]

        return ret

    def get_context_data_schema(
        self, service: ServiceSubClass
    ) -> Optional[Dict[str, Any]]:
        table = service.table
        if not table:
            return None

        properties = {}
        fields = FieldHandler().get_fields(table, specific=True)

        for field in fields:
            field_type = field_type_registry.get_by_model(field)
            if field_type.can_have_select_options:
                properties[field.db_column] = {
                    "type": "array",
                    "title": field.name,
                    "default": None,
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "id": {"type": "number"},
                            "color": {"type": "string"},
                        },
                    },
                }

        if len(properties) == 0:
            return None

        return {
            "type": "object",
            "title": self.get_schema_name(service),
            "properties": properties,
        }

    def get_json_type_from_response_serializer_field(
        self, field, field_type
    ) -> Dict[str, Any]:
        """
        Responsible for taking a `Field` and `FieldType`, getting the field type's
        response serializer field, and passing it into our serializer to JSON type
        mapping method, `guess_json_type_from_response_serializer_field`.

        :param field: The Baserow Field we want a type for.
        :param field_type: The Baserow FieldType we want a type for.
        :return: A dictionary to add to our schema.
        """

        serializer_field = field_type.get_response_serializer_field(field)
        return guess_json_type_from_response_serializer_field(serializer_field)


class LocalBaserowViewServiceType(LocalBaserowTableServiceType):
    """
    The `ServiceType` for `LocalBaserowViewService` subclasses.
    """

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["view"]

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + ["view_id"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            "view_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the Baserow view we want the data for.",
            ),
        }

    class SerializedDict(LocalBaserowTableServiceType.SerializedDict):
        view_id: int

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .select_related("view")
            .prefetch_related(
                "view__viewfilter_set",
                "view__filter_groups",
                "view__viewsort_set",
                "view__viewgroupby_set",
            )
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
    ):
        """
        Get the view ID from the mapping if it exists.
        """

        if prop_name == "view_id" and "database_views" in id_mapping:
            return id_mapping["database_views"].get(value, None)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[ServiceSubClass] = None,
    ) -> Dict[str, Any]:
        """Load the table & view instance instead of the ID."""

        # Call the super first as it'll fetch the table for us.
        values = super().prepare_values(values, user, instance)

        if "table" in values:
            # Reset the view if the table has changed
            if (
                "view_id" not in values
                and instance
                and instance.view_id
                and instance.view.table_id != values["table"].id
            ):
                values["view"] = None

        if "view_id" in values:
            view_id = values.pop("view_id")
            if view_id is not None:
                try:
                    view = ViewService().get_view(user, view_id)
                except ViewDoesNotExist:
                    raise DRFValidationError(
                        detail={
                            "detail": f"The view with ID {view_id} does not exist.",
                            "error": "view_does_not_exist",
                        },
                        code="view_does_not_exist",
                    )

                # If we're PATCHing with a `table_id` alongside the `view_id`,
                # validate with that table, otherwise we're PATCHing with just a
                # `view_id`, so we need to validate against the instance's table.
                table_to_validate = values.get(
                    "table", getattr(instance, "table", None)
                )

                # This isn't possible in the UI, but if a REST API request
                # sends us a `view_id` without a `table_id` existing on the
                # instance or in the values, we'll raise a 400.
                if not table_to_validate:
                    raise DRFValidationError(
                        detail={
                            "detail": "A table ID is required alongside the view ID.",
                            "error": "required",
                        },
                        code="required",
                    )

                # Check that the view table_id match the given table
                if view.table_id != table_to_validate.id:
                    raise DRFValidationError(
                        detail=f"The view with ID {view_id} is not related to the "
                        f"given table {table_to_validate.id}.",
                        code="invalid_view",
                    )
                else:
                    # Add the missing table
                    values["table"] = view.table
                values["view"] = view
            else:
                values["view"] = None

        return super().prepare_values(values, user, instance)


class LocalBaserowListRowsUserServiceType(
    ListServiceTypeMixin,
    LocalBaserowTableServiceSearchableMixin,
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSortableMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to a list of rows from the same Baserow instance as the
    one hosting the application.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_list_rows"
    model_class = LocalBaserowListRows
    max_result_limit = 200
    dispatch_type = DispatchTypes.DISPATCH_DATA_SOURCE

    @property
    def simple_formula_fields(self):
        return (
            super().simple_formula_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_simple_formula_fields
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceFilterableMixin.mixin_allowed_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_allowed_fields
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceSortableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_names
        )

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceSortableMixin.mixin_serializer_field_overrides,
            **LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceSortableMixin.SerializedDict,
        LocalBaserowTableServiceSearchableMixin.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
    ):
        pass

    def get_name_property(self, service: ServiceSubClass) -> Optional[str]:
        """
        Returns the primary field name.
        """

        if service.table_id:
            primary_field = service.table.field_set.filter(primary=True).first()
            return getattr(primary_field, "db_column", None)
        else:
            return None

    def import_path(self, path, id_mapping):
        """
        Updates the field ids in the path.
        """

        # If the path length is greater or equal to two, then we have
        # the current data source formula format of row, and field.
        if len(path) >= 2:
            row, field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently import properly, so we return the path as is.
            return path

        # If the field_dbname starts with anything other than "field_", it
        # implies that the path is not a valid one for this service type or the name
        # is the id.
        #
        # E.g. if the Page Designer changes a Data Source service type from
        # List Rows to Get Row, any Element using the Data Source will have
        # an invalid formula. E.g. instead of ["field_5165"], the path would
        # be [0, "field_5165"].
        #
        # When this is the case, do not attempt to import the formula.
        if not str(field_dbname).startswith("field_"):
            return path

        # Apply the mapping in case it is present for this field
        imported_field_dbname = (
            self.import_property_name(field_dbname, id_mapping) or field_dbname
        )

        return [row, imported_field_dbname, *rest]

    def import_context_path(
        self, path: List[str], id_mapping: Dict[int, int], **kwargs
    ):
        """
        Updates the field ids in the path.

        For context path data there is no row ID, as it represents the structure of the
        overall data, and not a specific row.
        """

        # Only process the path name if it includes at least one database field id
        if len(path) >= 1:
            field_dbname, *rest = path
        else:
            return path

        if field_dbname == "id":
            return path

        # Apply the mapping in case it is present for this field
        field_id = self.import_property_name(field_dbname, id_mapping)

        return [field_id, *rest]

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a set of unique field IDs.

        E.g. given that path is: ['*', 'field_5191'], returns the
        following: ['field_5191']

        Returns None if the Field ID is not found.

        The path can contain one or more parts, depending on the field type
        and the formula. Some examples of `path` are:

        An element that specifies a specific row and field:
        ['1', 'field_5439']

        An element that specifies a field and all rows:
        ['*', 'field_5439']

        An element that uses a Link Row Field formula
        ['0', 'field_5569', '0', 'value']
        """

        # If the path length is greater or equal to 1, then we have
        # the current data source formula format of row and field.

        if len(path) >= 2:
            row_id, field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently parse properly, so we return an empty list.
            return []

        # If the field_dbname doesn't start with "field_" and isn't "id" it probably
        # means that the formula is invalid.
        if not str(field_dbname).startswith("field_") and field_dbname != "id":
            return []

        return [field_dbname]

    def serialize_property(
        self,
        service: ServiceSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `filters` and `sortings` properties.

        :param service: The LocalBaserowListRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "filters":
            return self.serialize_filters(service)

        if prop_name == "sortings":
            return self.serialize_sortings(service)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
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
    ):
        """
        Responsible for deserializing the `filters` property.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        if prop_name == "filters":
            return self.deserialize_filters(value, id_mapping)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def dispatch_data(
        self,
        service: LocalBaserowListRows,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Returns a list of rows from the table stored in the service instance.

        :param service: the local baserow get row service.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: The context used for the dispatch.
        :return: The list of rows.
        """

        only_field_names = self.get_used_field_names(service, dispatch_context)

        table = resolved_values["table"]
        table_model = self.get_table_model(service)

        queryset = self.build_queryset(
            service, table, dispatch_context, model=table_model
        )

        if only_field_names is not None:
            # May be some fields were deleted in the meantime
            # Let's check we still have them
            available_fields = set(
                [fo["name"] for fo in self.get_table_field_objects(service)] + ["id"]
            )

            # Ensure that only used fields are fetched from the database.
            queryset = queryset.only(*available_fields.intersection(only_field_names))

        offset, count = dispatch_context.range(service)

        # We query one more row to be able to know if there is another page that can be
        # loaded.
        fake_count = min(self.max_result_limit, count) + 1

        rows = list(queryset[offset : offset + fake_count])

        has_next_page = len(rows) == fake_count

        return {
            "results": rows[:-1] if has_next_page else rows,
            "has_next_page": has_next_page,
            "baserow_table_model": table_model,
            "public_formula_fields": only_field_names,
        }

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> Any:
        """
        Given the rows found in `dispatch_data`, serializes them.

        :param dispatch_data: The data generated by `dispatch_data`.
        :return: The list of rows.
        """

        field_ids = (
            extract_field_ids_from_list(dispatch_data["public_formula_fields"])
            if isinstance(dispatch_data["public_formula_fields"], list)
            else None
        )

        serializer = get_row_serializer_class(
            dispatch_data["baserow_table_model"],
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
        )

        return {
            "results": serializer(dispatch_data["results"], many=True).data,
            "has_next_page": dispatch_data["has_next_page"],
        }

    def get_record_names(
        self,
        service: LocalBaserowListRows,
        record_ids: List[int],
        dispatch_context: DispatchContext,
    ) -> Dict[str, str]:
        """
        Return the record name associated with each one of the provided record ids.

        :param service: The table service.
        :param record_ids: A list containing the record identifiers.
        :param dispatch_context: The context used for the dispatch.
        :return: A dictionary mapping each record id to its name.
        :raises ServiceImproperlyConfigured: When service has no associated table.
        :raises ServiceImproperlyConfigured: When the table is trashed.
        """

        if not service.table_id:
            raise ServiceImproperlyConfigured("The table property is missing.")
        try:
            table = TableHandler().get_table(service.table_id)
            # NOTE: This is an expensive operation, so in the future we need to
            # calculate the list of used fields for searching/sorting/filtering
            # and pass them to `get_model`.
            # See: https://gitlab.com/baserow/baserow/-/issues/3062
            model = table.get_model()
            queryset = self.build_queryset(
                service, table, dispatch_context, model
            ).filter(pk__in=record_ids)
            record_names = {row.id: str(row) for row in queryset}
            return record_names
        except TableDoesNotExist as e:
            raise ServiceImproperlyConfigured("The specified table is trashed") from e


class LocalBaserowAggregateRowsUserServiceType(
    LocalBaserowTableServiceSearchableMixin,
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to aggregations over fields in a Baserow table or view.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_aggregate_rows"
    model_class = LocalBaserowAggregateRows
    dispatch_type = DispatchTypes.DISPATCH_DATA_SOURCE

    def get_schema_name(self, service: LocalBaserowAggregateRows) -> str:
        """
        The Local Baserow aggregation schema name added to the `title` in
        a JSON Schema object.

        :param service: The service we want to generate a schema `title` with.
        :return: A string.
        """

        return f"Aggregation{service.id}Schema"

    def generate_schema(
        self, service: LocalBaserowAggregateRows
    ) -> Optional[Dict[str, Any]]:
        """
        Responsible for generating a dictionary in the JSON Schema spec. Despite
        this service inheriting from `LocalBaserowTableServiceType`, it does not need
        to generate a schema for the table's fields. We instead want to generate
        a schema based on the service's aggregation type.

        :param service: A `LocalBaserowAggregateRows` instance.
        :return: A schema dictionary, or None if no `field` or `aggregation_type`
            have been applied.
        """

        if not service.field or not service.aggregation_type:
            return None

        # Pluck out the aggregation type which this service uses. We'll use its
        # `result_type` to inform the schema what the expected `result` format is.
        aggregation_type = field_aggregation_registry.get(service.aggregation_type)

        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                "result": {
                    "title": f"{service.field.name} result",
                    "type": aggregation_type.result_type,
                }
            },
        }

    def get_context_data(self, service: LocalBaserowAggregateRows) -> None:
        """
        The Local Baserow aggregate rows service type does not provide any
        `get_context_data` results.

        :param service: A LocalBaserowAggregateRows instance.
        :return: None
        """

        return None

    def get_context_data_schema(self, service: LocalBaserowAggregateRows) -> None:
        """
        The Local Baserow aggregate rows service type does not provide any
        `get_context_data_schema` results.

        :param service: A LocalBaserowAggregateRows instance.
        :return: None
        """

        return None

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).select_related("field")

    @property
    def simple_formula_fields(self):
        return (
            super().simple_formula_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_simple_formula_fields
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceFilterableMixin.mixin_allowed_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_allowed_fields
            + ["field", "aggregation_type"]
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_names
        ) + ["field_id", "aggregation_type"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            "field_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the Baserow field we want to aggregate on.",
            ),
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceSearchableMixin.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
    ):
        field_id: int
        aggregation_type: str

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[ServiceSubClass] = None,
    ) -> Dict[str, Any]:
        """
        Check if the aggregation and field combination is valid and
        reset any values that are no longer applicable.

        :param values: The values defining the
            aggregate rows service type.
        :param user: The user on whos behalf the aggregation is
            requested.
        :param instance: The service instance.
        """

        # The table and view will be prepared in the parent
        values = super().prepare_values(values, user, instance)

        if "table" in values:
            # Reset the field if the table has changed
            if (
                "table_id" not in values
                and instance
                and instance.field_id
                and instance.table_id != values["table"].id
            ):
                values["field"] = None

        if "field_id" in values:
            field = None
            field_id = values.pop("field_id")
            if field_id is not None:
                field = FieldHandler().get_field(field_id)
                # Validate against the `table` in the user-provided `values`,
                # otherwise validate against the persisted `instance.table`.
                table_to_validate = values.get(
                    "table", getattr(instance, "table", None)
                )
                if field.table_id == table_to_validate.id:
                    values["field"] = field
                else:
                    raise DRFValidationError(
                        detail=f"The field with ID {field_id} is not "
                        "related to the given table.",
                        code="invalid_field",
                    )

            # Aggregation types are always checked for compatibility
            # no matter if they have been already set previously
            aggregation_type = values.get(
                "aggregation_type", getattr(instance, "aggregation_type", "")
            )

            if aggregation_type and field:
                agg_type = field_aggregation_registry.get(aggregation_type)
                if not agg_type.field_is_compatible(field):
                    raise DRFValidationError(
                        detail=f"The field with ID {field_id} is not compatible "
                        f"with aggregation type {aggregation_type}.",
                        code="invalid_aggregation_raw_type",
                    )
                values["aggregation_type"] = aggregation_type
            else:
                values["aggregation_type"] = ""

        return super().prepare_values(values, user, instance)

    def serialize_property(
        self,
        service: ServiceSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `filters` properties.

        :param service: The LocalBaserowAggregateRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "filters":
            return self.serialize_filters(service)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
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
    ):
        """
        Responsible for deserializing the `filters` and `field_id` properties.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        if prop_name == "filters":
            return self.deserialize_filters(value, id_mapping)

        if prop_name == "field_id":
            return id_mapping.get("database_fields", {}).get(value, value)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def resolve_service_formulas(
        self,
        service: LocalBaserowAggregateRows,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        A hook called before the `LocalBaserowTableServiceType` subclass dispatch
        calls. It ensures we check the service has a `Field` and aggregation type
        before execution.

        :param service: A `LocalBaserowAggregateRows` instance.
        :param dispatch_context: The dispatch_context instance used to
            resolve formulas (if any).
        :raises ServiceImproperlyConfigured: When we try and dispatch a service that
            has no `Field` associated with it, or if aggregation type is invalid.
        """

        # We need a valid field to dispatch with.
        if not service.field:
            raise ServiceImproperlyConfigured("The field property is missing.")

        # We need a valid aggregation type to dispatch with.
        try:
            field_aggregation_registry.get(service.aggregation_type)
        except AggregationTypeDoesNotExist as exc:
            raise ServiceImproperlyConfigured(exc.args[0]) from exc

        return super().resolve_service_formulas(service, dispatch_context)

    def dispatch_data(
        self,
        service: LocalBaserowAggregateRows,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Returns a field aggregation from the table stored in the service instance.

        :param service: the local baserow aggregate rows service.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: The context used for the dispatch.
        :return: Aggregations.
        """

        try:
            table = resolved_values["table"]
            if service.field.trashed:
                raise ServiceImproperlyConfigured(
                    f"The field with ID {service.field.id} is trashed."
                )
            field = service.field
            model = self.get_table_model(service)
            model_field = model._meta.get_field(field.db_column)
            queryset = self.build_queryset(
                service, table, dispatch_context, model=model
            )
            agg_type = field_aggregation_registry.get(service.aggregation_type)
            result = agg_type.aggregate(queryset, model_field, field)

            return {
                "data": {"result": result},
                "baserow_table_model": model,
            }
        except DjangoFieldDoesNotExist as ex:
            raise ServiceImproperlyConfigured(
                f"The field with ID {service.field_id} does not exist."
            ) from ex
        except IncompatibleField as ex:
            raise ServiceImproperlyConfigured(
                f"The field with ID {service.field_id} is not compatible "
                f"with the aggregation type {service.aggregation_type}"
            ) from ex

    def dispatch_transform(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Responsible for transforming the data returned by the `dispatch_data`
        method into a format that can be used by the frontend.

        :param data: The data generated by `dispatch_data`.
        :return: A dictionary containing the aggregation result.
        """

        return data["data"]

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
        """
        Returns the usual properties for this service type.
        """

        if path[0] == "result":
            return ["result"]

        return []


class LocalBaserowGetRowUserServiceType(
    LocalBaserowTableServiceSearchableMixin,
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSortableMixin,
    LocalBaserowTableServiceSpecificRowMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to one specific row from a given table from the same
    Baserow instance as the one hosting the application.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_get_row"
    model_class = LocalBaserowGetRow
    dispatch_type = DispatchTypes.DISPATCH_DATA_SOURCE

    @property
    def simple_formula_fields(self):
        return (
            super().simple_formula_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_simple_formula_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_simple_formula_fields
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceFilterableMixin.mixin_allowed_fields
            + LocalBaserowTableServiceSearchableMixin.mixin_allowed_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_allowed_fields
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_names
        )

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            **LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_overrides,
            **LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_overrides,
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceSearchableMixin.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
        LocalBaserowTableServiceSpecificRowMixin.SerializedDict,
    ):
        pass

    def import_path(self, path, id_mapping):
        """
        Updates the field ids in the path.
        """

        # If the path length is greater or equal to one, then we have
        # the GetRow data source formula format of `data_source.PK.field`.
        if len(path) >= 1:
            field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently import properly, so we return the path as is.
            return path

        # If the field_dbname starts with anything other than "field_", it
        # implies that the path is not a valid one for this service type.
        #
        # E.g. if the Page Designer changes a Data Source service type from
        # List Rows to Get Row, any Element using the Data Source will have
        # an invalid formula. E.g. instead of ["field_5165"], the path would
        # be [0, "field_5165"].
        #
        # When this is the case, do not attempt to import the formula.
        if not str(field_dbname).startswith("field_"):
            return path

        # Import the mapped field from the ID mapping.
        imported_field_dbname = (
            self.import_property_name(field_dbname, id_mapping) or field_dbname
        )

        return [imported_field_dbname, *rest]

    def import_context_path(
        self, path: List[str], id_mapping: Dict[int, int], **kwargs
    ):
        """
        Update the field ids in the path, similar to `import_path` method.
        """

        return self.import_path(path, id_mapping)

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a set of unique field names.

        E.g. given that path is: ['field_5191', 'prop1', '*', 'value'], returns the
        following: ['field_5191']

        Returns an empty list if the field name isn't found.
        """

        # If the path length is greater or equal to one, then we have
        # the current data source formula format of field and may be something else.
        if len(path) >= 1:
            field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently parse it properly, so we return an empty list.
            return []

        # If the field_dbname doesn't start with "field_" or isn't "id" it probably
        # means that the formula is invalid.
        if not str(field_dbname).startswith("field_") and field_dbname != "id":
            return []

        return [field_dbname]

    def serialize_property(
        self,
        service: ServiceSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `filters`.

        :param service: The LocalBaserowListRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "filters":
            return self.serialize_filters(service)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
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
    ):
        """
        Get the view & table ID from the mapping if it exists and also updates the
        row_id, search_query & filters formulas.
        """

        if prop_name == "filters":
            return self.deserialize_filters(value, id_mapping)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> Any:
        """
        Responsible for serializing the `dispatch_data` row.

        :param dispatch_data: The `dispatch_data` result.
        :return:
        """

        field_ids = (
            extract_field_ids_from_list(dispatch_data["public_formula_fields"])
            if isinstance(dispatch_data["public_formula_fields"], list)
            else None
        )

        serializer = get_row_serializer_class(
            dispatch_data["baserow_table_model"],
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
        )

        serialized_row = serializer(dispatch_data["data"]).data

        return serialized_row

    def resolve_service_formulas(
        self,
        service: ServiceSubClass,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        :param service: A `LocalBaserowTableService` instance.
        :param dispatch_context: The dispatch_context instance used to
            resolve formulas (if any).
        :raises ServiceImproperlyConfigured: When we try and dispatch a service that
            has no `Table` associated with it.
        """

        resolved_values = super().resolve_service_formulas(service, dispatch_context)
        return self.resolve_row_id(resolved_values, service, dispatch_context)

    def dispatch_data(
        self,
        service: LocalBaserowGetRow,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Returns the row targeted by the `row_id` formula from the table stored in the
        service instance.

        :param service: the local baserow get row service.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: The context used for the dispatch.
        :return: The rows.
        """

        table = resolved_values["table"]
        only_field_names = self.get_used_field_names(service, dispatch_context)

        table_model = self.get_table_model(service)

        queryset = self.build_queryset(service, table, dispatch_context, table_model)

        # If no row id is provided return the first item from the queryset
        # This is useful when we want to use filters to specifically choose one
        # row by setting the right condition
        if "row_id" not in resolved_values:
            if not queryset.exists():
                raise DoesNotExist()
            return {
                "data": queryset.first(),
                "baserow_table_model": table_model,
                "public_formula_fields": only_field_names,
            }

        try:
            row = queryset.get(pk=resolved_values["row_id"])
            return {
                "data": row,
                "baserow_table_model": table_model,
                "public_formula_fields": only_field_names,
            }
        except table_model.DoesNotExist:
            raise DoesNotExist()


class LocalBaserowUpsertRowServiceType(
    LocalBaserowTableServiceType, LocalBaserowTableServiceSpecificRowMixin
):
    """
    A `LocalBaserow` service type which will create or update rows in
    the service's target table when it is used in conjunction with
    workflow actions.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_upsert_row"
    model_class = LocalBaserowUpsertRow
    dispatch_type = DispatchTypes.DISPATCH_WORKFLOW_ACTION

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_allowed_fields
        )

    @property
    def simple_formula_fields(self):
        return (
            super().simple_formula_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_simple_formula_fields
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + ["field_mappings"]
            + LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_names
        )

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            "field_mappings": LocalBaserowTableServiceFieldMappingSerializer(
                many=True,
                required=False,
                help_text="The field mapping associated with this service.",
            ),
            **LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_overrides,
        }

    class SerializedDict(
        LocalBaserowTableServiceType.SerializedDict,
        LocalBaserowTableServiceSpecificRowMixin.SerializedDict,
    ):
        field_mappings: List[Dict]

    def after_update(
        self,
        instance: LocalBaserowUpsertRow,
        values: Dict,
        changes: Dict[str, Tuple],
    ):
        """
        Responsible for managing the upsert row's field mappings following
        a successful service update.

        :param instance: The updated service instance.
        :param values: The values that were passed when creating the service
            metadata.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        if "field_mappings" in values and instance.table_id:
            bulk_field_mappings = []
            # Bulk delete the existing field mappings on the service.
            # We'll bulk create the mappings in the values `field_mappings`.
            instance.field_mappings.all().delete()
            # The queryset we'll use to narrow down the `get_field` query,
            # this ensures we find the field within the service's table.
            base_field_qs = instance.table.field_set.all()
            field_mappings = values.get("field_mappings", [])
            for field_mapping in field_mappings:
                try:
                    field = FieldHandler().get_field(
                        field_mapping["field_id"], base_queryset=base_field_qs
                    )
                except KeyError:
                    raise DRFValidationError("A field mapping must have a `field_id`.")
                except FieldDoesNotExist as exc:
                    raise DRFValidationError(str(exc))

                bulk_field_mappings.append(
                    LocalBaserowTableServiceFieldMapping(
                        field=field,
                        service=instance,
                        enabled=field_mapping["enabled"],
                        value=field_mapping["value"],
                    )
                )
            LocalBaserowTableServiceFieldMapping.objects.bulk_create(
                bulk_field_mappings
            )

    def formula_generator(
        self, service: ServiceType
    ) -> Generator[str | Instance, str, None]:
        """
        A generator to iterate over all formulas related to a
        LocalBaserowTableServiceType.

        The manner in which formula fields are stored will vary for each class
        that implements LocalBaserowTableServiceType. E.g. a formula might be
        a direct attribute of the class (e.g. value) or it might be in a
        related model (e.g. field_mappings).
        """

        yield from super().formula_generator(service)

        # Return field_mapping formulas
        for field_mapping in service.field_mappings.all():
            new_formula = yield field_mapping.value
            if new_formula is not None:
                field_mapping.value = new_formula
                yield field_mapping

    def serialize_property(
        self,
        service: LocalBaserowUpsertRow,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "field_mappings":
            return [
                {
                    "field_id": m.field_id,
                    "value": m.value,
                    "enabled": m.enabled,
                }
                for m in service.field_mappings.all()
            ]

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
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
    ):
        """
        Responsible for deserializing the `field_mappings`, if they're present.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        if prop_name == "field_mappings":
            return [
                {
                    **item,
                    "field_id": (
                        # The `database_fields` exist, but the field ID
                        # won't be present if it's trashed.
                        id_mapping["database_fields"].get(item["field_id"])
                        if "database_fields" in id_mapping
                        else item["field_id"]
                    ),
                }
                for item in value
            ]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Responsible for creating the service, and then if `field_mappings`
        are present, creating them in bulk.

        :param serialized_values: The serialized service data.
        :return: The newly created service instance.
        """

        field_mappings = serialized_values.pop("field_mappings", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # Create the field mappings.
        # We don't create any field mappings if the `field_id` is `None`,
        # this will happen if we've exported a workspace's applications
        # and the field was trashed. The imported application's field mapping
        # will be skipped.
        LocalBaserowTableServiceFieldMapping.objects.bulk_create(
            [
                LocalBaserowTableServiceFieldMapping(
                    **field_mapping,
                    service=service,
                )
                for field_mapping in field_mappings
                if field_mapping["field_id"] is not None
            ]
        )

        return service

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).prefetch_related("field_mappings")

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> Any:
        """
        Responsible for serializing the `dispatch_data` row.

        :param dispatch_data: The `dispatch_data` result.
        :return:
        """

        serializer = get_row_serializer_class(
            dispatch_data["baserow_table_model"],
            RowSerializer,
            is_response=True,
        )
        serialized_row = serializer(dispatch_data["data"]).data

        return serialized_row

    def resolve_service_formulas(
        self,
        service: LocalBaserowUpsertRow,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        :param service: A `LocalBaserowTableService` instance.
        :param dispatch_context: The dispatch_context instance used to
            resolve formulas (if any).
        :raises ServiceImproperlyConfigured: When we try and dispatch a service that
            has no `Table` associated with it.
        """

        resolved_values = super().resolve_service_formulas(service, dispatch_context)
        dispatch_context.reset_call_stack()  # Before resolving the row_id
        resolved_values = self.resolve_row_id(
            resolved_values, service, dispatch_context
        )

        field_mappings = service.field_mappings.select_related("field").all()
        for field_mapping in field_mappings:
            dispatch_context.reset_call_stack()
            try:
                resolved_values[field_mapping.id] = resolve_formula(
                    field_mapping.value,
                    formula_runtime_function_registry,
                    dispatch_context,
                )
            except DataProviderChunkInvalidException as e:
                message = (
                    "Path error in formula for "
                    f"field {field_mapping.field.name}({field_mapping.field.id})"
                )
                raise ServiceImproperlyConfigured(message) from e
            except Exception as e:
                message = (
                    "Unknown error in formula for "
                    f"field {field_mapping.field.name}({field_mapping.field.id}): {repr(e)} - {str(e)}"
                )
                raise ServiceImproperlyConfigured(message) from e

        return resolved_values

    def dispatch_data(
        self,
        service: LocalBaserowUpsertRow,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Responsible for creating a new row, or updating an existing row if a row ID has
        been provided, in this `LocalBaserowUpsertRow` service's table.

        :param service: the local baserow upsert row service.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: the context used for formula resolution.
        :return: The created or updated rows.
        """

        table = resolved_values["table"]
        integration = service.integration.specific
        row_id: Optional[int] = resolved_values.get("row_id", None)

        row_values = {}
        field_mappings = service.field_mappings.select_related("field").filter(
            enabled=True
        )

        for field_mapping in field_mappings:
            if field_mapping.id not in resolved_values:
                continue

            field = field_mapping.field
            field_type = field_type_registry.get_by_model(field.specific_class)

            # Determine if the field type is read only, if so, skip it. This
            # is here for defensive programming purposes, when a field is converted
            # to a read only type, the field mapping is destroyed. This check is just
            # in case a loophole is found.
            if field_type.read_only:
                continue

            resolved_value = resolved_values[field_mapping.id]

            # Transform and validate the resolved value with the field type's DRF field.
            serializer_field = field_type.get_serializer_field(field.specific)
            try:
                # Automatically cast the resolved value to the serializer field type
                cast_function = guess_cast_function_from_response_serializer_field(
                    serializer_field
                )
                if cast_function:
                    resolved_value = cast_function(resolved_value)
                resolved_value = serializer_field.run_validation(resolved_value)
            except (ValidationError, DRFValidationError) as exc:
                raise ServiceImproperlyConfigured(
                    "The result value of the formula is not valid for the "
                    f"field `{field.name} ({field.db_column})`: {str(exc)}"
                ) from exc

            # Then transform and validate the resolved value for prepare value for db.
            try:
                field_type.prepare_value_for_db(field.specific, resolved_value)
                row_values[field.db_column] = resolved_value
            except ValidationError as exc:
                raise ServiceImproperlyConfigured(
                    "The result value of the formula is not valid for the "
                    f"field `{field.name} ({field.db_column})`: {exc.message}"
                ) from exc

        model = table.get_model()

        if row_id:
            try:
                (row,) = UpdateRowsActionType.do(
                    integration.authorized_user,
                    table,
                    rows_values=[{**row_values, "id": row_id}],
                    model=model,
                )
            except RowDoesNotExist as exc:
                raise ServiceImproperlyConfigured(
                    f"The row with id {row_id} does not exist."
                ) from exc
        else:
            try:
                (row,) = CreateRowsActionType.do(
                    user=integration.authorized_user,
                    table=table,
                    rows_values=[row_values],
                    model=model,
                )
            except CannotCreateRowsInTable as exc:
                raise ServiceImproperlyConfigured(
                    f"Cannot create rows in table {table.id} because it has a data sync."
                ) from exc

        return {"data": row, "baserow_table_model": model}

    def import_path(self, path, id_mapping):
        """
        Updates the field ids in the path.
        """

        # If the path length is greater or equal to one, then we have
        # the current data source formula format of row, and field.
        if len(path) >= 1:
            field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently import properly, so we return the path as is.
            return path

        if field_dbname == "id":
            return path

        # Import the mapped field from the ID mapping.
        imported_field_dbname = (
            self.import_property_name(field_dbname, id_mapping) or field_dbname
        )

        return [imported_field_dbname, *rest]

    def import_context_path(
        self, path: List[str], id_mapping: Dict[int, int], **kwargs
    ):
        """
        Updates the field ids in the path, similar to `import_path` method.
        """

        return self.import_path(path, id_mapping)


class LocalBaserowDeleteRowServiceType(
    LocalBaserowTableServiceType, LocalBaserowTableServiceSpecificRowMixin
):
    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_delete_row"
    model_class = LocalBaserowDeleteRow
    dispatch_type = DispatchTypes.DISPATCH_WORKFLOW_ACTION

    @property
    def simple_formula_fields(self):
        return (
            super().simple_formula_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_simple_formula_fields
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceSpecificRowMixin.mixin_allowed_fields
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_names
        )

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceSpecificRowMixin.mixin_serializer_field_overrides,
        }

    class SerializedDict(
        LocalBaserowTableServiceType.SerializedDict,
        LocalBaserowTableServiceSpecificRowMixin.SerializedDict,
    ):
        pass

    def resolve_service_formulas(
        self,
        service: LocalBaserowDeleteRow,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        :param service: A `LocalBaserowTableService` instance.
        :param dispatch_context: The dispatch_context instance used to
            resolve formulas (if any).
        :raises ServiceImproperlyConfigured: When we try and dispatch a service that
            has no `Table` associated with it.
        """

        resolved_values = super().resolve_service_formulas(service, dispatch_context)
        return self.resolve_row_id(resolved_values, service, dispatch_context)

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> Response:
        """
        The delete row action's `dispatch_data` will contain an empty
        `data` dictionary. When we get to this method and wish to transform
        the data, we can simply return a 204 response.

        :param dispatch_data: The `dispatch_data` result.
        :return: A 204 response.
        """

        return Response(status=204)

    def dispatch_data(
        self,
        service: LocalBaserowDeleteRow,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Responsible for deleting a specific row if a row ID has been provided,
        in this `LocalBaserowDeleteRow` service's table.

        :param service: the local baserow delete row service.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: the context used for formula resolution.
        :return: A dictionary with empty `data`.
        """

        table = resolved_values["table"]
        integration = service.integration.specific
        row_id: Optional[int] = resolved_values.get("row_id", None)
        model = table.get_model()

        if row_id:
            try:
                DeleteRowsActionType.do(
                    integration.authorized_user, table, [row_id], model=model
                )
            except RowDoesNotExist as exc:
                raise ServiceImproperlyConfigured(
                    f"The row with id {row_id} does not exist."
                ) from exc
            except CannotDeleteRowsInTable as exc:
                raise ServiceImproperlyConfigured(
                    f"Cannot delete rows in table {table.id} because it has a data sync."
                ) from exc

        return {"data": {}, "baserow_table_model": model}
