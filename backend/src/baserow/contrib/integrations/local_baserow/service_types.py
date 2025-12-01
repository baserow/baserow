from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import FieldDoesNotExist as DjangoFieldDoesNotExist
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.dispatch import Signal

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

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
from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
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
from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_deleted,
    rows_updated,
)
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.table.service import TableService
from baserow.contrib.database.views.exceptions import (
    AggregationTypeDoesNotExist,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY
from baserow.contrib.database.views.service import ViewService
from baserow.contrib.database.views.view_aggregations import (
    DistributionViewAggregationType,
)
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
    LocalBaserowRowsCreated,
    LocalBaserowRowsDeleted,
    LocalBaserowRowsUpdated,
    LocalBaserowTableService,
    LocalBaserowTableServiceFieldMapping,
    LocalBaserowUpsertRow,
    Service,
)
from baserow.contrib.integrations.local_baserow.utils import (
    guess_cast_function_from_response_serializer_field,
    guess_json_type_from_response_serializer_field,
)
from baserow.core.cache import global_cache
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.handler import CoreHandler
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import (
    DispatchTypes,
    ListServiceTypeMixin,
    ServiceType,
    TriggerServiceTypeMixin,
)
from baserow.core.services.types import (
    DispatchResult,
    FormulaToResolve,
    ServiceDict,
    ServiceSubClass,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.types import PermissionCheck

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel, Table


SCHEMA_CACHE_TTL = 60 * 60  # 1 hour


class LocalBaserowServiceType(ServiceType):
    """
    The `ServiceType` for all `LocalBaserow` integration services.
    """

    integration_type = LocalBaserowIntegrationType.type

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
    # table_id is needed to check configuration
    public_serializer_field_names = ["table_id"]
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

    def _convert_allowed_field_names(self, service, allowed_fields):
        """
        Convert the `field_x` to human fields.
        """

        mapping = {
            field_obj["field"].db_column: field_obj["field"].name
            for field_obj in self.get_table_field_objects(service) or []
        }
        return [mapping.get(f, f) for f in allowed_fields]

    def sanitize_result(self, service, result, allowed_field_names):
        """
        Remove the non public fields from the result.
        """

        allowed_field_names = self._convert_allowed_field_names(
            service, allowed_field_names
        )

        return super().sanitize_result(service, result, allowed_field_names)

    def prepare_value_path(self, service: Service, path: List[str]):
        if len(path) < 1:
            return path

        db_column, *rest = path

        human_name = db_column

        for field_obj in self.get_table_field_objects(service) or []:
            if field_obj["field"].db_column == db_column:
                human_name = field_obj["field"].name
                break

        return [human_name, *rest]

    def _prepare_one_row(self, mapping, row):
        def convert(key, value):
            if key in mapping:
                return mapping[key]["type"].to_runtime_formula_value(
                    mapping[key]["field"], value
                )
            return value

        return {key: convert(key, value) for key, value in row.items()}

    def _prepare_result(self, table_model, dispatch_result):
        mapping = {
            field_obj["field"].name: field_obj
            for field_obj in table_model.get_field_objects() or []
        }

        if self.returns_list:
            return {
                **dispatch_result,
                "results": [
                    self._prepare_one_row(mapping, r)
                    for r in dispatch_result["results"]
                ],
            }

        else:
            return self._prepare_one_row(mapping, dispatch_result)

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

        queryset = self.get_table_queryset(service, table, dispatch_context, model)
        return queryset

    def get_table_queryset(
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
            if only_field_names is not None
            else None
        )

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .select_related(
                "table__database__workspace",
                "table__data_sync",
            )
        )

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
        :raises ServiceImproperlyConfiguredDispatchException: When we try and dispatch
            a service that has no `Table` associated with it, or if the table/database
            is trashed.
        """

        if service.table_id is None:
            raise ServiceImproperlyConfiguredDispatchException("No table selected")

        if TrashHandler.item_has_a_trashed_parent(service.table, check_item_also=True):
            raise ServiceImproperlyConfiguredDispatchException(
                "The selected table is trashed"
            )

        return super().resolve_service_formulas(service, dispatch_context)

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

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a set of unique field IDs.

        E.g. given that path is: ['field_5191', 'something'], returns the
        following: ['field_5191']

        Returns None if the Field ID is not found.

        The path can contain one or more parts, depending on the field type
        and the formula. Some examples of `path` are:

        An element that specifies a specific a field:
        ['field_5439']

        An element that uses a Link Row Field formula
        ['field_5569', '0', 'value']
        """

        # If the path length is greater or equal to 1, then we have
        # the current data source formula format of row and field.

        if len(path) >= 1:
            field_dbname, *rest = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently parse properly, so we return an empty list.
            return []

        # If the field_dbname doesn't start with "field_" and isn't "id" it probably
        # means that the formula is invalid.
        if not str(field_dbname).startswith("field_") and field_dbname != "id":
            return []

        return [field_dbname]

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

    def export_prepared_values(self, instance: Service) -> dict[str, any]:
        values = super().export_prepared_values(instance)
        if values.get("integration"):
            del values["integration"]
            values["integration_id"] = instance.integration.id
        if values.get("table"):
            del values["table"]
            values["table_id"] = instance.table.id if instance.table else None
        return values

    def generate_schema(
        self, service: ServiceSubClass, allowed_fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Responsible for generating a dictionary in the JSON Schema spec. This helps
        inform the frontend data source form and data explorer about the type of
        schema the service is interacting with.

        :param service: A `LocalBaserowTableService` subclass.
        :param allowed_fields: The properties which are allowed to be included in the
            generated schema.
        :return: A schema dictionary, or None if no `Table` has been applied.
        """

        if service.table_id is None:
            return None

        properties = global_cache.get(
            f"table_{service.table_id}__service_schema",
            default=lambda: self._get_table_properties(service),
            invalidate_key=f"table_{service.table_id}__service_invalidate_key",
            timeout=SCHEMA_CACHE_TTL,
        )

        # When a schema is being generated, we will exclude properties that the
        # Application creator did not actively configure. A configured property
        # is one that the Application is using in a formula, configuration
        # setting, or schema property.
        if allowed_fields is not None:
            allowed_fields = set(allowed_fields)
            properties = {
                field: value
                for field, value in properties.items()
                if field in allowed_fields
            }

        return self.get_schema_for_return_type(service, properties)

    def _get_table_properties(
        self, service: ServiceSubClass
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the properties from the table model fields.

        :param service: A `LocalBaserowTableService` subclass.
        :return: A schema dictionary, or None if no `Table` has been applied.
        """

        field_objects = self.get_table_field_objects(service)

        if field_objects is None:
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
        for field_object in field_objects:
            field_type = field_object["type"]
            # Only `TextField` has a default value at the moment.
            field = field_object["field"]
            default_value = getattr(field, "text_default", None)
            field_serializer = field_type.get_serializer(field, FieldSerializer)
            properties[field.db_column] = {
                "title": field.name,
                "default": default_value,
                "searchable": field_type.is_searchable(field)
                and field_type.type
                not in self.unsupported_adhoc_searchable_field_types,
                "sortable": field_type.check_can_order_by(field, DEFAULT_SORT_TYPE_KEY)
                and field_type.type not in self.unsupported_adhoc_sortable_field_types,
                "filterable": field_type.check_can_filter_by(field)
                and field_type.type
                not in self.unsupported_adhoc_filterable_field_types,
                "original_type": field_type.type,
                "metadata": field_serializer.data,
            } | self.get_json_type_from_response_serializer_field(field, field_type)

        return properties

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

        if isinstance(dispatch_context.public_allowed_properties, dict):
            return dispatch_context.public_allowed_properties.get("all", {}).get(
                service.id, []
            )

        return None

    def get_table_model(
        self, service: LocalBaserowTableService
    ) -> Optional["GeneratedTableModel"]:
        """
        Returns the model for the table associated with the given service.
        """

        if not service.table_id:
            return None

        return service.table.get_model()

    def get_table_field_objects(
        self, service: LocalBaserowTableService
    ) -> List[Dict] | None:
        """
        Returns the fields objects of the table of the given service.

        :param service: The service we want the fields for.
        :returns: The field objects from the table model.
        """

        model = self.get_table_model(service)

        if model is None:
            return None

        return model.get_field_objects()

    def get_context_data(
        self, service: ServiceSubClass, allowed_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if service.table_id is None:
            return None

        context_data = global_cache.get(
            f"table_{service.table_id}__service_context_data",
            default=lambda: self._get_context_data(service),
            invalidate_key=f"table_{service.table_id}__service_invalidate_key",
            timeout=SCHEMA_CACHE_TTL,
        )

        # When a context_data is being generated, we will exclude properties that
        # the Application creator did not actively configure. A configured property
        # is one that the Application is using in a formula, configuration
        # setting, or schema property.
        if allowed_fields is not None:
            allowed_fields = set(allowed_fields)
            context_data = {
                field: value
                for field, value in context_data.items()
                if field in allowed_fields
            }

        return context_data

    def _get_context_data(self, service: ServiceSubClass) -> Dict[str, Any]:
        field_objects = self.get_table_field_objects(service)

        if field_objects is None:
            return None

        ret = {}
        for field_object in field_objects:
            field_type = field_object["type"]
            if field_type.can_have_select_options:
                field_serializer = field_type.get_serializer(
                    field_object["field"], FieldSerializer
                )
                ret[field_object["name"]] = field_serializer.data["select_options"]

        return ret

    def get_context_data_schema(
        self, service: ServiceSubClass, allowed_fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        if service.table_id is None:
            return None

        properties = global_cache.get(
            f"table_{service.table_id}__service_context_data_schema",
            default=lambda: self._get_context_data_properties(service),
            invalidate_key=f"table_{service.table_id}__service_invalidate_key",
            timeout=SCHEMA_CACHE_TTL,
        )

        if allowed_fields is not None:
            allowed_fields = set(allowed_fields)
            properties = {
                field: value
                for field, value in properties.items()
                if field in allowed_fields
            }

        if len(properties) == 0:
            return None

        return {
            "type": "object",
            "title": self.get_schema_name(service),
            "properties": properties,
        }

    def _get_context_data_properties(
        self, service: ServiceSubClass
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the context data properties for the table associated with the service.
        """

        field_objects = self.get_table_field_objects(service)

        if field_objects is None:
            return None

        properties = {}
        for field_object in field_objects:
            if field_object["type"].can_have_select_options:
                properties[field_object["name"]] = {
                    "type": "array",
                    "title": field_object["field"].name,
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

        return properties

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
                except ViewDoesNotExist as exc:
                    raise DRFValidationError(
                        detail={
                            "detail": f"The view with ID {view_id} does not exist.",
                            "error": "view_does_not_exist",
                        },
                        code="view_does_not_exist",
                    ) from exc

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

    def export_prepared_values(self, instance: Service) -> dict[str, any]:
        values = super().export_prepared_values(instance)
        if values.get("view"):
            del values["view"]
            values["view_id"] = instance.view.id
        return values


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

    type = "local_baserow_list_rows"
    model_class = LocalBaserowListRows
    dispatch_types = [
        DispatchTypes.DATA,
        DispatchTypes.ACTION,
    ]
    serializer_mixins = (
        LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins
        + LocalBaserowTableServiceSortableMixin.mixin_serializer_mixins
    )

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
            + ["default_result_count"]
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceSortableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_names
            + ["default_result_count"]
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
        default_result_count: int

    def get_max_result_limit(self, service: Service):
        return settings.INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT

    def get_default_result_limit(self, service: Service):
        return service.default_result_count

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

        offset, count = dispatch_context.range(service)

        if count is None:
            count = self.get_default_result_limit(service)

        if count == 0:
            # Shortcut to prevent further computations for this DS as we don't want to
            # return results
            return None

        only_field_names = self.get_used_field_names(service, dispatch_context)

        table = service.table
        table_model = self.get_table_model(service)

        queryset = self.build_queryset(
            service, table, dispatch_context, model=table_model
        )

        if only_field_names is not None:
            # Maybe some fields were deleted in the meantime
            # Let's check we still have them
            available_fields = set(
                [fo["name"] for fo in (self.get_table_field_objects(service) or [])]
                + ["id"]
            )

            # Ensure that only used fields are fetched from the database.
            queryset = queryset.only(
                # We keep the order field here as the serializer needs it
                *available_fields.intersection(only_field_names),
                "order",
            )

        if dispatch_context.only_record_id is not None:
            queryset = queryset.filter(id=dispatch_context.only_record_id)

        # We query one more row to be able to know if there is another page that can be
        # loaded.
        fake_count = min(self.get_max_result_limit(service), count) + 1

        rows = list(queryset[offset : offset + fake_count])

        has_next_page = len(rows) == fake_count

        return {
            "results": rows[:-1] if has_next_page else rows,
            "has_next_page": has_next_page,
            "baserow_table_model": table_model,
            "public_allowed_properties": only_field_names,
        }

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> DispatchResult:
        """
        Given the rows found in `dispatch_data`, serializes them.

        :param dispatch_data: The data generated by `dispatch_data`.
        :return: The list of rows.
        """

        if dispatch_data is None:
            return DispatchResult(
                data={
                    "results": [],
                    "has_next_page": False,
                }
            )

        field_ids = (
            extract_field_ids_from_list(dispatch_data["public_allowed_properties"])
            if isinstance(dispatch_data["public_allowed_properties"], list)
            else None
        )

        serializer = get_row_serializer_class(
            dispatch_data["baserow_table_model"],
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
            user_field_names=True,
        )

        result = self._prepare_result(
            dispatch_data["baserow_table_model"],
            {
                "results": serializer(dispatch_data["results"], many=True).data,
                "has_next_page": dispatch_data["has_next_page"],
            },
        )

        return DispatchResult(data=result)

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
        :raises ServiceImproperlyConfiguredDispatchException: When service has no
            associated table.
        :raises ServiceImproperlyConfiguredDispatchException: When the table is trashed.
        """

        if not service.table_id:
            raise ServiceImproperlyConfiguredDispatchException("No table selected")
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
            raise ServiceImproperlyConfiguredDispatchException(
                "The selected table is trashed"
            ) from e


class LocalBaserowAggregateRowsUserServiceType(
    LocalBaserowTableServiceSearchableMixin,
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to aggregations over fields in a Baserow table or view.
    """

    type = "local_baserow_aggregate_rows"
    model_class = LocalBaserowAggregateRows
    dispatch_types = [
        DispatchTypes.DATA,
        DispatchTypes.ACTION,
    ]
    serializer_mixins = LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins

    # Local Baserow aggregate rows does not currently support the distribution
    # aggregation type, this will be resolved in a future release.
    unsupported_aggregation_types = [DistributionViewAggregationType.type]

    def get_schema_name(self, service: LocalBaserowAggregateRows) -> str:
        """
        The Local Baserow aggregation schema name added to the `title` in
        a JSON Schema object.

        :param service: The service we want to generate a schema `title` with.
        :return: A string.
        """

        return f"Aggregation{service.id}Schema"

    def generate_schema(
        self,
        service: LocalBaserowAggregateRows,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Responsible for generating a dictionary in the JSON Schema spec. Despite
        this service inheriting from `LocalBaserowTableServiceType`, it does not need
        to generate a schema for the table's fields. We instead want to generate
        a schema based on the service's aggregation type.

        :param service: A `LocalBaserowAggregateRows` instance.
        :param allowed_fields: The properties which are allowed to be included in the
            generated schema.
        :return: A schema dictionary, or None if no `field` or `aggregation_type`
            have been applied.
        """

        if not service.field or not service.aggregation_type:
            return None

        # The `result` must be an allowed field, otherwise we have no schema.
        if allowed_fields is not None and "result" not in allowed_fields:
            return {}

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

    def get_context_data(
        self,
        service: LocalBaserowAggregateRows,
        allowed_fields: Optional[List[str]] = None,
    ) -> dict:
        context_data = {}
        if service.field and not (
            allowed_fields is not None and "result" not in allowed_fields
        ):
            serialized_field = field_type_registry.get_serializer(
                service.field, FieldSerializer
            ).data
            context_data["field"] = serialized_field
        return context_data

    def get_context_data_schema(
        self, service: LocalBaserowAggregateRows
    ) -> dict | None:
        return None

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related("field__table__database")
        )

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
            **LocalBaserowTableServiceSearchableMixin.mixin_serializer_field_overrides,
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

        # Aggregation types are always checked for compatibility
        # no matter if they have been already set previously
        aggregation_type = values.get(
            "aggregation_type", getattr(instance, "aggregation_type", "")
        )

        if aggregation_type in self.unsupported_aggregation_types:
            raise DRFValidationError(
                detail=f"The {aggregation_type} aggregation type "
                "is not currently supported.",
                code="unsupported_aggregation_type",
            )

        if "table" in values:
            # Reset the field if the table has changed
            if (
                "table_id" not in values
                and instance
                and instance.field_id
                and instance.table != values["table"]
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

    def export_prepared_values(self, instance: Service) -> dict[str, any]:
        values = super().export_prepared_values(instance)
        if values.get("field"):
            del values["field"]
            values["field_id"] = instance.field.id
        return values

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
        :raises ServiceImproperlyConfiguredDispatchException: When we try and dispatch
            a service that has no `Field` associated with it, or if aggregation type
            is invalid.
        """

        # We need a valid field to dispatch with.
        if not service.field:
            raise ServiceImproperlyConfiguredDispatchException(
                "The field property is missing."
            )

        # We need a valid aggregation type to dispatch with.
        try:
            field_aggregation_registry.get(service.aggregation_type)
        except AggregationTypeDoesNotExist as exc:
            raise ServiceImproperlyConfiguredDispatchException(exc.args[0]) from exc

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

        only_field_names = self.get_used_field_names(service, dispatch_context)
        if only_field_names and "result" not in only_field_names:
            return {"data": {"result": None}}

        try:
            table = service.table
            if service.field.trashed:
                raise ServiceImproperlyConfiguredDispatchException(
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
            raise ServiceImproperlyConfiguredDispatchException(
                f"The field with ID {service.field_id} does not exist."
            ) from ex
        except IncompatibleField as ex:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The field with ID {service.field_id} is not compatible "
                f"with the aggregation type {service.aggregation_type}"
            ) from ex

    def dispatch_transform(
        self,
        data: Dict[str, Any],
    ) -> DispatchResult:
        """
        Responsible for transforming the data returned by the `dispatch_data`
        method into a format that can be used by the frontend.

        :param data: The data generated by `dispatch_data`.
        :return: A dictionary containing the aggregation result.
        """

        return DispatchResult(data=data["data"])

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

    type = "local_baserow_get_row"
    model_class = LocalBaserowGetRow
    dispatch_types = [
        DispatchTypes.DATA,
        DispatchTypes.ACTION,
    ]
    serializer_mixins = (
        LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins
        + LocalBaserowTableServiceSortableMixin.mixin_serializer_mixins
    )

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

        table = service.table
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
                "public_allowed_properties": only_field_names,
            }

        try:
            row = queryset.get(pk=resolved_values["row_id"])
            return {
                "data": row,
                "baserow_table_model": table_model,
                "public_allowed_properties": only_field_names,
            }
        except table_model.DoesNotExist:
            raise DoesNotExist()

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> DispatchResult:
        """
        Responsible for serializing the `dispatch_data` row.

        :param dispatch_data: The `dispatch_data` result.
        :return:
        """

        field_ids = (
            extract_field_ids_from_list(dispatch_data["public_allowed_properties"])
            if isinstance(dispatch_data["public_allowed_properties"], list)
            else None
        )

        serializer = get_row_serializer_class(
            dispatch_data["baserow_table_model"],
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
            user_field_names=True,
        )

        serialized_row = self._prepare_result(
            dispatch_data["baserow_table_model"], serializer(dispatch_data["data"]).data
        )

        return DispatchResult(data=serialized_row)


class LocalBaserowUpsertRowServiceType(
    LocalBaserowTableServiceSpecificRowMixin, LocalBaserowTableServiceType
):
    """
    A `LocalBaserow` service type which will create or update rows in
    the service's target table when it is used in conjunction with
    workflow actions.
    """

    type = "local_baserow_upsert_row"
    model_class = LocalBaserowUpsertRow
    dispatch_types = [DispatchTypes.ACTION]

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
            new_formula = yield BaserowFormulaObject.to_formula(field_mapping.value)
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

    def formulas_to_resolve(
        self, service: LocalBaserowUpsertRow
    ) -> list[FormulaToResolve]:
        """
        Returns the formula to resolve for this service.
        """

        field_mappings = (
            service.field_mappings.select_related("field")
            .exclude(field__trashed=True)
            .all()
        )
        formulas = []
        for field_mapping in field_mappings:
            formulas.append(
                FormulaToResolve(
                    field_mapping.id,
                    field_mapping.value,
                    lambda x: x,
                    f'field "{field_mapping.field.name}"',
                ),
            )

        return super().formulas_to_resolve(service) + formulas

    def _get_validation_details(self, error):
        detail = error.detail

        if isinstance(detail, str):
            return detail
        elif isinstance(detail, list):
            return str(detail[0]) if detail else ""
        elif isinstance(detail, dict):
            for field, errors in detail.items():
                if isinstance(errors, list) and errors:
                    return str(errors[0])
                else:
                    return str(errors)
        return str(detail)

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

        table = service.table
        used_field_names = self.get_used_field_names(service, dispatch_context)

        service.integration = service.integration.specific
        row_id: Optional[int] = resolved_values.get("row_id", None)

        row_values = {}
        field_mappings = (
            service.field_mappings.select_related("field")
            .filter(enabled=True)
            .exclude(field__trashed=True)
        )

        # Track the field<->mapping relationship.
        context_map = {fm.field: fm for fm in field_mappings}

        # Perform a bulk permission check on each field-mapping field.
        permission_check_results = CoreHandler().check_multiple_permissions(
            [
                PermissionCheck(
                    service.integration.authorized_user,
                    WriteFieldValuesOperationType.type,
                    fm.field,
                )
                for fm in field_mappings
            ],
            workspace=service.integration.application.workspace,
        )

        # Only iterate over field mappings which we know our authorized user is
        # allowed to write values to. Writable doesn't refer to the field type being
        # writable, but rather if the authorized user has the correct permission.
        authorized_user_writable_field_mappings = [
            context_map[check.context]
            for check, check_result in permission_check_results.items()
            if check_result
        ]

        for field_mapping in authorized_user_writable_field_mappings:
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
                    serializer_field, service
                )

                if cast_function:
                    resolved_value = cast_function(resolved_value)
                resolved_value = serializer_field.run_validation(resolved_value)
            except ValidationError as exc:
                raise InvalidContextContentDispatchException(
                    f'Value error for field "{field.name}": {exc.message}'
                ) from exc
            except DRFValidationError as exc:
                raise InvalidContextContentDispatchException(
                    f'Value error for field "{field.name}"'
                    f": {self._get_validation_details(exc)}"
                ) from exc

            # Then transform and validate the resolved value for prepare value for db.
            try:
                field_type.prepare_value_for_db(field.specific, resolved_value)
                row_values[field.db_column] = resolved_value
            except ValidationError as exc:
                raise InvalidContextContentDispatchException(
                    f'Value error for field "{field.name}": {exc.message}'
                ) from exc

        model = table.get_model()

        if row_id:
            try:
                (row,) = UpdateRowsActionType.do(
                    service.integration.authorized_user,
                    table,
                    rows_values=[{**row_values, "id": row_id}],
                    model=model,
                ).updated_rows
            except RowDoesNotExist as exc:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The row with id {row_id} does not exist."
                ) from exc
        else:
            try:
                (row,) = CreateRowsActionType.do(
                    user=service.integration.authorized_user,
                    table=table,
                    rows_values=[row_values],
                    model=model,
                )
            except CannotCreateRowsInTable as exc:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"Cannot create rows in table {table.id} because "
                    "it has a data sync."
                ) from exc

        return {
            "data": row,
            "baserow_table_model": model,
            "public_formula_fields": used_field_names,
        }

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> DispatchResult:
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
            user_field_names=True,
        )

        serialized_row = self._prepare_result(
            dispatch_data["baserow_table_model"], serializer(dispatch_data["data"]).data
        )

        return DispatchResult(data=serialized_row)

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
    LocalBaserowTableServiceSpecificRowMixin, LocalBaserowTableServiceType
):
    type = "local_baserow_delete_row"
    model_class = LocalBaserowDeleteRow
    dispatch_types = [DispatchTypes.ACTION]

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

        table = service.table
        integration = service.integration.specific
        row_id: Optional[int] = resolved_values.get("row_id", None)
        model = table.get_model()

        if row_id:
            try:
                DeleteRowsActionType.do(
                    integration.authorized_user, table, [row_id], model=model
                )
            except RowDoesNotExist as exc:
                raise DoesNotExist(f"The row with id {row_id} does not exist.") from exc
            except CannotDeleteRowsInTable as exc:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"Cannot delete rows in table {table.id} because "
                    "it has a data sync."
                ) from exc

        return {"data": {}, "baserow_table_model": model}

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> DispatchResult:
        """
        The delete row action's `dispatch_data` will contain an empty
        `data` dictionary. When we get to this method and wish to transform
        the data, we can simply return a 204 response.

        :param dispatch_data: The `dispatch_data` result.
        :return: A dispatch result with no data, and a 204 status code.
        """

        return DispatchResult(status=204)


class LocalBaserowRowsSignalServiceType(
    TriggerServiceTypeMixin, LocalBaserowTableServiceType
):
    # The signal that this service type is called by.
    signal: Signal = None

    # Local Baserow signal services (e.g. rows created, updated, deleted)
    # all return an array of rows, even if only a single row is affected.
    # We set `returns_list` to `True` so that when we generate the schema,
    # the `type` is set to `array` instead of `object`.
    returns_list = True

    def start_listening(self, on_event: Callable):
        super().start_listening(on_event)
        self.signal.connect(self._signal_receiver)

    def stop_listening(self):
        self.signal.disconnect(self._signal_receiver)

    def _process_event(self, *args, **kwargs):
        return self.on_event(*args, **kwargs) if callable(self.on_event) else None

    def _handle_signal(
        self,
        sender,
        user: AbstractUser,
        rows: QuerySet["GeneratedTableModel"],
        table: "Table",
        model: "GeneratedTableModel",
        **kwargs,
    ):
        def get_data():
            # Make sure we have an up to date model
            local_model = model.baserow_table.get_model()

            serializer = get_row_serializer_class(
                local_model, RowSerializer, is_response=True, user_field_names=True
            )

            data_to_process = {
                "results": serializer(rows, many=True).data,
                "has_next_page": False,
            }

            return self._prepare_result(local_model, data_to_process)

        self._process_event(
            self.model_class.objects.filter(table=table),
            get_data,
            user=user,
        )

    def _signal_receiver(self, *args, **kwargs):
        transaction.on_commit(lambda: self._handle_signal(*args, **kwargs))

    def import_context_path(
        self, path: List[str], id_mapping: Dict[int, int], **kwargs
    ):
        """
        Updates the field ids in the path, similar to `import_path` method.
        """

        return self.import_path(path, id_mapping)

    def import_path(self, path, id_mapping):
        """
        Import Local Baserow signal service types paths.
        """

        # All Local Baserow signal service types have a length of 3:
        # {previousNodeId}.{rowIndex}.{fieldName}. By this point, we should
        # only have two parts: {rowIndex}.{fieldName}.
        if len(path) == 2:
            index, field_dbname = path
        else:
            # In any other scenario, we have a formula that is not a format we
            # can currently import properly, so we return the path as is.
            return path

        # When this is the case, do not attempt to import the formula.
        if not str(field_dbname).startswith("field_"):
            return path

        # Apply the mapping in case it is present for this field
        imported_field_dbname = (
            self.import_property_name(field_dbname, id_mapping) or field_dbname
        )

        return [index, imported_field_dbname]


class LocalBaserowRowsCreatedServiceType(LocalBaserowRowsSignalServiceType):
    signal = rows_created
    type = "local_baserow_rows_created"
    model_class = LocalBaserowRowsCreated


class LocalBaserowRowsUpdatedServiceType(LocalBaserowRowsSignalServiceType):
    signal = rows_updated
    type = "local_baserow_rows_updated"
    model_class = LocalBaserowRowsUpdated


class LocalBaserowRowsDeletedServiceType(LocalBaserowRowsSignalServiceType):
    signal = rows_deleted
    type = "local_baserow_rows_deleted"
    model_class = LocalBaserowRowsDeleted
