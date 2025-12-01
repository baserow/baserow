from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from functools import cached_property
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from django import db
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import connection, router, transaction
from django.db.models import Field as DjangoField
from django.db.models import Model, Q, QuerySet, Window
from django.db.models.expressions import RawSQL
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.functions import RowNumber
from django.utils.encoding import force_str

from celery.utils import chunks
from opentelemetry import metrics, trace

from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.dependencies.update_collector import (
    DependencyContext,
    FieldUpdateCollector,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDataConstraintException,
    FieldNotInTable,
    IncompatibleField,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.constants import (
    CREATED_BY_COLUMN_NAME,
    LAST_MODIFIED_BY_COLUMN_NAME,
)
from baserow.contrib.database.table.models import (
    FieldObject,
    GeneratedTableModel,
    Table,
)
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    ImportRowsDatabaseTableOperationType,
)
from baserow.contrib.database.table.signals import table_updated
from baserow.contrib.database.trash.models import TrashedRows
from baserow.contrib.database.views.operations import (
    CreateViewRowOperationType,
    DeleteViewRowOperationType,
    ReadViewRowOperationType,
    UpdateViewRowOperationType,
)
from baserow.contrib.database.views.registries import view_ownership_type_registry
from baserow.core.db import (
    get_highest_order_of_queryset,
    get_unique_orders_before_item,
    recalculate_full_orders,
)
from baserow.core.exceptions import (
    CannotCalculateIntermediateOrder,
    PermissionDenied,
    PermissionException,
)
from baserow.core.handler import CoreHandler
from baserow.core.psycopg import is_unique_violation_error, sql
from baserow.core.registries import OperationType
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.handler import TrashHandler
from baserow.core.trash.registries import trash_item_type_registry
from baserow.core.types import PermissionCheck
from baserow.core.utils import Progress, get_non_unique_values, grouper

from .constants import ROW_IMPORT_CREATION, ROW_IMPORT_VALIDATION
from .error_report import RowErrorReport
from .exceptions import InvalidRowLength, RowDoesNotExist, RowIdsNotUnique
from .operations import (
    DeleteDatabaseRowOperationType,
    MoveRowDatabaseRowOperationType,
    ReadDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from .signals import (
    before_rows_create,
    before_rows_delete,
    before_rows_update,
    row_orders_recalculated,
    rows_created,
    rows_deleted,
    rows_updated,
)
from .types import (
    CreatedRowsData,
    FieldsMetadata,
    FileImportConfiguration,
    GeneratedTableModelForUpdate,
    RowId,
    RowsForUpdate,
    UpdatedRowsData,
)

if TYPE_CHECKING:
    from django.db.backends.utils import CursorWrapper

    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.views.models import View

tracer = trace.get_tracer(__name__)

BATCH_SIZE = 1024

meter = metrics.get_meter(__name__)
rows_created_counter = meter.create_counter(
    "baserow.rows_created",
    unit="1",
    description="The number of rows created in user tables.",
)
rows_updated_counter = meter.create_counter(
    "baserow.rows_updated",
    unit="1",
    description="The number of rows updated in user tables.",
)
rows_deleted_counter = meter.create_counter(
    "baserow.rows_deleted",
    unit="1",
    description="The number of rows deleted in user tables.",
)


def serialize_errors_recursive(error):
    if isinstance(error, dict):
        return {
            key: serialize_errors_recursive(errors) for key, errors in error.items()
        }
    elif isinstance(error, list):
        return [serialize_errors_recursive(errors) for errors in error]
    else:
        if isinstance(error, ValidationError):
            return {"error": error.message, "code": error.code}
        if isinstance(error, Exception):
            return {"error": force_str(error), "code": "unknown_error"}
        return error


def prepare_field_errors(field_errors):
    """
    Here we update the index generated by the call of the create_rows method because
    that method received only valid rows so the index might be incorrect.
    """

    if not field_errors:
        return None

    return {
        field: serialize_errors_recursive(errs) for field, errs in field_errors.items()
    }


class RowM2MChangeTracker:
    def __init__(self):
        self._deleted_m2m_rels: Dict[
            str, Dict["DjangoField", Dict[GeneratedTableModel, Set[int]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        self._created_m2m_rels: Dict[
            str, Dict["DjangoField", Dict[GeneratedTableModel, Set[int]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    def track_m2m_update_for_field_and_row(
        self,
        field: "DjangoField",
        field_name: str,
        row: GeneratedTableModel,
        new_values: Iterable[int],
    ):
        field_type = field_type_registry.get_by_model(field)
        if field_type.is_many_to_many_field:
            # Uses the existing prefetch cache and so doesn't run queries.
            m2m_rels_before_update = {r.id for r in getattr(row, field_name).all()}
            set_of_new_values = set(new_values)
            self._deleted_m2m_rels[field_type.type][field][row] = (
                m2m_rels_before_update - set_of_new_values
            )
            self._created_m2m_rels[field_type.type][field][row] = (
                set_of_new_values - m2m_rels_before_update
            )

    def track_m2m_created_for_new_row(
        self,
        row: GeneratedTableModel,
        field: "DjangoField",
        new_values: Iterable[Union[int, Model]],
    ):
        field_type = field_type_registry.get_by_model(field)
        if new_values and isinstance(new_values[0], Model):
            new_values = [v.id for v in new_values]
        if field_type.is_many_to_many_field:
            self._created_m2m_rels[field_type.type][field][row] = set(new_values)

    def get_deleted_m2m_rels_per_field_id_for_type(
        self, field_type: str
    ) -> Dict[int, Set[int]]:
        return self._deleted_m2m_rels[field_type]

    def get_created_m2m_rels_per_field_for_type(
        self, field_type
    ) -> Dict["DjangoField", Dict[GeneratedTableModel, Set[int]]]:
        return self._created_m2m_rels[field_type]

    def get_deleted_link_row_rels_for_update_collector(
        self,
    ) -> Dict[int, Set[int]]:
        from baserow.contrib.database.fields.field_types import LinkRowFieldType

        return {
            field.id: set().union(*list(deleted_rels_per_row.values()))
            for field, deleted_rels_per_row in self._deleted_m2m_rels[
                LinkRowFieldType.type
            ].items()
        }


class RowHandler(metaclass=baserow_trace_methods(tracer)):
    def prepare_values(self, fields, values):
        """
        Prepares a set of values so that they can be created or updated in the database.
        It will check if the value can actually be set and prepares the value based on
        the field type.

        :param fields: The returned fields object from the get_model method.
        :type fields: dict
        :param values: The values that need to be prepared with the field id or the
            string 'field_{id}' as key.
        :type values: dict
        :return: The prepared values with the field name as key.
        :rtype: dict
        """

        return {
            field["name"]: field["type"].prepare_value_for_db(
                field["field"],
                values[field_id] if field_id in values else values[field["name"]],
            )
            for field_id, field in fields.items()
            if field_id in values or field["name"] in values
        }

    def prepare_values_with_defaults(
        self, field_objects: Dict[int, FieldObject], rows_values: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Iterate over the rows and add the default values for the fields that are not
        present in the row values and have a default value. This is used when creating
        new rows, but it shouldn't be used when updating rows because it will override
        the values that are already set.

        :param field_objects: The field objects for a model.
        :param rows_values: The rows and their values that need to be prepared. Note
            that it will be modified in place.
        :return: The prepared values for all rows in the same structure as it was
        """

        for row_value in rows_values:
            for field_obj in field_objects.values():
                field_name = field_obj["name"]
                field_type = field_obj["type"]
                field = field_obj["field"]
                if field_name not in row_value:
                    default_value = field_type.get_default_value(field)
                    if default_value is not None:
                        row_value[field_name] = default_value
        return rows_values

    def prepare_rows_in_bulk(
        self,
        field_objects: Dict[int, FieldObject],
        rows_values: List[Dict[str, Any]],
        generate_error_report: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
        """
        Prepares a set of values in bulk for all rows so that they can be created or
        updated in the database. It will check if the values can actually be set and
        prepares them based on their field type.

        :param field_objects: The returned fields object from the get_model method.
        :param rows_values: The rows and their values that need to be prepared.
        :param generate_error_report: If set to True, the method will return an
            object that contains information about the errors that
            occurred during the rows preparation.
        :return: The prepared values for all rows in the same structure as it was
            passed in.
        """

        field_ids = {}
        prepared_values_by_field = defaultdict(dict)

        # organize values by field name
        for index, row_value in enumerate(rows_values):
            for field_id, field_obj in field_objects.items():
                field_name = field_obj["name"]
                field_type = field_obj["type"]
                field = field_obj["field"]
                field_ids[field_name] = field_id
                if field_name in row_value:
                    prepared_values_by_field[field_name][index] = row_value[field_name]

        # bulk-prepare values per field
        for field_name, batch_values in prepared_values_by_field.items():
            field_obj = field_objects[field_ids[field_name]]
            field_type = field_obj["type"]
            field = field_obj["field"]
            prepared_values_by_field[
                field_name
            ] = field_type.prepare_value_for_db_in_bulk(
                field, batch_values, continue_on_error=generate_error_report
            )

        # replace original values to keep ordering
        prepared_rows = []
        failing_rows = {}
        for index, row_value in enumerate(rows_values):
            new_values = deepcopy(row_value)
            row_errors = {}
            for field_id, field_obj in field_objects.items():
                field_name = field_obj["name"]
                if field_name in row_value:
                    prepared_value = prepared_values_by_field[field_name][index]
                    if isinstance(prepared_value, Exception):
                        row_errors[field_name] = [prepared_value]
                    else:
                        new_values[field_name] = prepared_value
            if not row_errors:
                prepared_rows.append(new_values)
            else:
                failing_rows[index] = row_errors

        return prepared_rows, failing_rows

    def extract_field_ids_from_keys(self, keys: List[str]) -> List[int]:
        """
        Extracts the field ids from a list of field names.
        For example keys like 'field_2', '3', 4 will be seen ass field ids.

        :param keys: The list of field names.
        :return: A list containing the field ids as integers.
        """

        ids = [get_field_id_from_field_key(v) for v in keys]
        return [_id for _id in ids if _id is not None]

    def extract_field_ids_from_dict(self, values: Dict[str, Any]) -> List[int]:
        """
        Extracts the field ids from a dict containing the values that need to
        updated. For example keys like 'field_2', '3', 4 will be seen ass field ids.

        :param values: The values where to extract the fields ids from.
        :return: A list containing the field ids as integers.
        """

        return self.extract_field_ids_from_keys(values.keys())

    def get_internal_values_for_fields(
        self,
        row: GeneratedTableModel,
        updated_field_ids: Set[int],
    ) -> Dict[str, Any]:
        """
        Gets the current values of the row before the update.

        :param row: The row instance.
        :param updated_field_ids: The fields ids that need to be exported.
        :return: The current values of the row before the update.
        """

        values = {}
        for field_id in updated_field_ids:
            field_object = row.get_field_object_by_id(field_id, include_trash=True)
            field_type = field_object["type"]
            if field_type.read_only:
                continue
            field_name = field_object["name"]
            field_value = field_type.get_internal_value_from_db(row, field_name)
            values[field_name] = field_value
        return values

    def extract_manytomany_values(
        self, values: Dict[str, Any], model: "GeneratedTableModel"
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Split the row values and the many_to_many values from the prepared
        values because they need to be created and updated in a different way
        compared to a regular value.

        :param values: The values where to extract the manytomany values from.
        :param model: The model containing the fields. The key, which is also
            the field name, is used to check in the model if the value is a
            ManyToMany value.
        :return: The row_values without the manytomany values and the manytomany
            values in another dict.
        """

        manytomany_values = {}
        row_values = {}

        for name, value in values.items():
            model_field = model._meta.get_field(name)
            if isinstance(model_field, ManyToManyField):
                manytomany_values[name] = values[name]
            else:
                row_values[name] = value

        return row_values, manytomany_values

    def get_unique_orders_before_row(
        self,
        before_row: Optional[GeneratedTableModel],
        model: Type[GeneratedTableModel],
        amount: int = 1,
    ) -> List[Decimal]:
        """
        Calculates a list of unique decimal orders that can safely be used before the
        provided `before_row` or at the end of the table, depending on whether the
        `before_row` value is provided.

        Note that this method can trigger an update of all the rows in the table in
        the event all the orders must be recalculated.

        :param before_row: The row instance where the before orders must be
            calculated for. If `None`, then it's assumed that the orders are for
            the end of the table.
        :param model: The model of the related table
        :param amount: The number of orders that must be requested. Can be higher if
            multiple rows are inserted or moved.
        :return: A list of decimals containing safe to use orders in order.
        """

        queryset = model.objects

        if before_row:
            try:
                return get_unique_orders_before_item(
                    before_row, queryset, amount=amount
                )
            except CannotCalculateIntermediateOrder:
                # If the `find_intermediate_order` fails with a
                # `CannotCalculateIntermediateOrder`, it means that it's not possible
                # calculate an intermediate fraction. Therefore, must reset all the
                # orders of the table (while respecting their original order),
                # so that we can then can find the fraction any many more after.
                self.recalculate_row_orders(model.baserow_table, model)
                # Refresh the row element as its order might have changed
                before_row.refresh_from_db()
                return get_unique_orders_before_item(
                    before_row, queryset, amount=amount
                )
        else:
            # If no `before` is provided, we can just find the highest value and
            # add one to it.
            return get_highest_order_of_queryset(queryset, amount=amount)

    def get_row(
        self,
        user: AbstractUser,
        table: Table,
        row_id: int,
        model: Optional[Type[GeneratedTableModel]] = None,
        base_queryset: Optional[QuerySet] = None,
        view: Optional["View"] = None,
    ) -> GeneratedTableModel:
        """
        Fetches a single row from the provided table.

        :param user: The user of whose behalf the row is requested.
        :param table: The table where the row must be fetched from.
        :param row_id: The id of the row that must be fetched.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param base_queryset: A queryset that can be used to already pre-filter
            the results.
        :param view: Optionally provide view, if the row is fetched in the view.
            This can result in different permissions checks.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        :return: The requested row instance.
        """

        self._check_permissions_with_view_fallback(
            ReadDatabaseRowOperationType.type,
            ReadViewRowOperationType.type,
            user,
            table,
            view,
            [row_id],
        )

        if model is None:
            model = table.get_model()

        if base_queryset is None:
            base_queryset = model.objects

        try:
            row = base_queryset.get(id=row_id)
        except model.DoesNotExist:
            raise RowDoesNotExist(row_id)

        return row

    def get_adjacent_row(
        self,
        table_model,
        row_id,
        previous=False,
        view=None,
        search=None,
        search_mode=None,
    ):
        """
        Fetches the adjacent row of the provided row in the provided table. By default,
        the next row is fetched, but this can be changed by setting `previous` to True.
        If a view is provided, the adjacent row will be fetched based on the ordering
        and filtering of the view. If a search is provided, the adjacent row will be
        fetched based on the search results. If no view or search is provided, the
        adjacent row will be fetched based on the table's ordering.

        :param table_model: The model of the table where the row must be fetched from.
        :param row_id: The id of the row where the adjacent row must be fetched from.
        :param previous: If the previous row should be fetched.
        :param view: The view that was used to fetch the row. If provided, the adjacent
            row will be fetched based on the ordering and filtering of the view.
        :param search: The search query that was used to fetch the row. If provided,
            the adjacent row will be fetched based on the search results.
        :param search_mode: The search mode that was used to fetch the row. If
            provided, the adjacent row will be fetched based on the search results.
        :return: The adjacent row instance if any, None otherwise.
        """

        from baserow.contrib.database.views.handler import ViewHandler

        if view is not None:
            queryset = ViewHandler().get_queryset(None, view, model=table_model)
        else:
            queryset = table_model.objects.all().enhance_by_fields()

        if search is not None:
            queryset = queryset.search_all_fields(search, search_mode=search_mode)

        return self.get_adjacent_row_in_queryset(queryset, row_id, previous=previous)

    def get_adjacent_row_in_queryset(self, queryset, row_id, previous=False):
        """
        Fetches the adjacent row of the provided row in the provided queryset. By
        default, the next row is fetched, but this can be changed by setting `previous`
        to True.

        :param queryset: The queryset that was used to fetch the row. This should
            contain all the orders, annotations, filters that were used when fetching
            the row.
        :param row_id: The id of the row where the adjacent row must be fetched from.
        :param previous: If the previous row should be fetched.
        :return: The adjacent row.
        :raise RowDoesNotExist: When the row with the provided id does not exist.
        """

        table_model = queryset.model
        try:
            row = queryset.get(pk=row_id)
        except table_model.DoesNotExist:
            raise RowDoesNotExist(row_id)

        order_bys = queryset.query.order_by or table_model._meta.ordering
        queryset_with_row_nr = queryset.annotate(
            row_nr=Window(expression=RowNumber(), order_by=order_bys)
        ).values("id", "row_nr")

        sql, params = queryset_with_row_nr.query.get_compiler(
            connection=connection
        ).as_sql()

        adjacent_id_subquery = f"""
            WITH ordered AS ({sql})
            SELECT id FROM ordered
            WHERE row_nr = (SELECT row_nr FROM ordered WHERE id = %s)
            {'-' if previous else '+'} 1
        """  # nosec B608

        return table_model.objects.filter(
            id=RawSQL(adjacent_id_subquery, (*params, row.id))  # nosec B611
        ).first()

    def get_row_for_update(
        self,
        user: AbstractUser,
        table: Table,
        row_id: int,
        enhance_by_fields: bool = False,
        model: Optional[Type[GeneratedTableModel]] = None,
    ) -> GeneratedTableModelForUpdate:
        """
        Fetches a single row from the provided table and lock it for update.

        :param user: The user of whose behalf the row is requested.
        :param table: The table where the row must be fetched from.
        :param row_id: The id of the row that must be fetched.
        :param enhance_by_fields: Enhances the queryset based on the
            `enhance_queryset` for each field in the table.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        :return: The requested row instance.
        """

        if model is None:
            model = table.get_model()

        base_queryset = model.objects.select_for_update(of=("self",))
        if enhance_by_fields:
            base_queryset = base_queryset.enhance_by_fields()

        row = self.get_row(
            user,
            table,
            row_id,
            model=model,
            base_queryset=base_queryset,
        )

        return cast(GeneratedTableModelForUpdate, row)

    def get_row_names(
        self, table: "Table", row_ids: List[int], model: "GeneratedTableModel" = None
    ) -> Dict[str, str]:
        """
        Returns the row names for all row ids specified in `row_ids` parameter from
        the given table.

        :param table: The table where the rows must be fetched from.
        :param row_ids: The id of the rows that must be fetched.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :return: A dict of the requested rows names. The key are the row ids and the
            values are the row names.
        """

        if not model:
            primary_field = table.field_set.get(primary=True)
            model = table.get_model(
                field_ids=[], fields=[primary_field], add_dependencies=False
            )

        queryset = model.objects.filter(pk__in=row_ids)

        return {row.id: str(row) for row in queryset}

    # noinspection PyMethodMayBeStatic
    def has_row(self, user, table, row_id, raise_error=False, model=None):
        """
        Checks if a row with the given id exists and is not trashed in the table.

        This method is preferred over using get_row when you do not actually need to
        access any values of the row as it will not construct a full model but instead
        do a much more efficient query to check only if the row exists or not.

        :param user: The user of whose behalf the row is being checked.
        :type user: User
        :param table: The table where the row must be checked in.
        :type table: Table
        :param row_id: The id of the row that must be checked.
        :type row_id: int
        :param raise_error: Whether or not to raise an Exception if the row does not
            exist or just return a boolean instead.
        :type raise_error: bool
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :type model: Model
        :raises RowDoesNotExist: When the row with the provided id does not exist
            and raise_error is set to True.
        :raises UserNotInWorkspace: If the user does not belong to the workspace.
        :return: If raise_error is False then a boolean indicating if the row does or
            does not exist.
        :rtype: bool
        """

        CoreHandler().check_permissions(
            user,
            ReadDatabaseRowOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        if model is None:
            model = table.get_model(field_ids=[])

        row_exists = model.objects.filter(id=row_id).exists()
        if not row_exists and raise_error:
            raise RowDoesNotExist(row_id)
        else:
            return row_exists

    def _check_permissions_with_view_fallback(
        self,
        table_operation: OperationType,
        view_operation: OperationType,
        user: AbstractUser,
        table: Table,
        view: Optional["View"],
        row_ids: Optional[List[int]] = None,
    ):
        """
        Checks if the user has permission to the provided table object. If not, it will
        fall back to the view permissions, if the view ownership type allows modifying
        rows, the check if it has permissions to the view.

        :param table_operation: The permission on table level to check. If this check
            passes, then no exception will be raised.
        :param view_operation: The permission on view level to check.  If this both
            this check succeed and the view ownership type allows modifying rows, then
            no exception will be raised.
        :param user: The user on whose behalf the permissions are checked.
        :param table: The table where to check the permissions for.
        :param view: Optionally provide the view where to check permissions for as
            fallback.
        :param row_ids: Optionally the row ids that are modified.
        :raises PermissionDenied: If the user does not have access to both the table
            and view.
        :return:
        """

        table_check = PermissionCheck(
            user,
            table_operation,
            context=table,
        )
        view_check = PermissionCheck(
            user,
            view_operation,
            context=view,
        )

        checks = [table_check]
        if view is not None:
            checks.append(view_check)

        # Check multiple permissions regardless because if a view is provided, we don't
        # want to execute multiple queries in order to check if the permission check
        # should fall back on the view.
        check_results = CoreHandler().check_multiple_permissions(
            checks,
            workspace=table.database.workspace,
            return_permissions_exceptions=True,
        )

        if check_results[table_check] is True:
            return

        if (
            view is not None
            # Because the user wants to change rows in a specific table, we must make
            # sure that the provided view belongs to that table. Otherwise, it would
            # result in a security bug.
            and view.table_id == table.id
            # The view ownership type should also allow modifying rows directly in
            # the view. The rows are provided because some additional permission
            # checks might need to be done in order to make sure that the user is
            # allowed to modify the provided rows.
            and view_ownership_type_registry.get(view.ownership_type).can_modify_rows(
                view,
                row_ids,
            )
            and check_results[view_check] is True
        ):
            return

        if isinstance(check_results[table_check], PermissionException):
            raise check_results[table_check]

        if isinstance(check_results[view_check], PermissionException):
            raise check_results[view_check]

        raise PermissionDenied(actor=user)

    def create_row(
        self,
        user: AbstractUser,
        table: Table,
        values: Optional[Dict[str, Any]] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        before_row: Optional[GeneratedTableModel] = None,
        view: Optional["View"] = None,
        user_field_names: bool = False,
        values_already_prepared: bool = False,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModel:
        """
        Creates a new row for a given table with the provided values if the user
        belongs to the related workspace. It also calls the rows_created signal.

        :param user: The user of whose behalf the row is created.
        :param table: The table for which to create a row for.
        :param values: The values that must be set upon creating the row. The keys must
            be the field ids.
        :param model: If a model is already generated it can be provided here to avoid
            having to generate the model again.
        :param before_row: If provided the new row will be placed right before that row
            instance.
        :param view: Optionally provide view, if the row is created in the view.
            This can result in different permissions checks.
        :param user_field_names: Whether or not the values are keyed by the internal
            Baserow field name (field_1,field_2 etc) or by the user field names.
        :param values_already_prepared: Whether or not the values are already sanitized
            and validated for every field and can be used directly by the handler
            without any further check.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :return: The created row instance.
        """

        if model is None:
            model = table.get_model()

        self._check_permissions_with_view_fallback(
            CreateRowDatabaseTableOperationType.type,
            CreateViewRowOperationType.type,
            user,
            table,
            view,
        )

        if not values:
            values = {}

        self._check_write_fields_values_permissions(user, model, [values])

        return self.force_create_row(
            user,
            table,
            values,
            model,
            before_row,
            user_field_names,
            values_already_prepared=values_already_prepared,
            send_webhook_events=send_webhook_events,
        )

    def force_create_row(
        self,
        user: AbstractUser,
        table: Table,
        values: Optional[Dict[str, Any]] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        before: Optional[GeneratedTableModel] = None,
        user_field_names: bool = False,
        values_already_prepared: bool = False,
        send_webhook_events: bool = True,
    ):
        """
        Creates a new row for a given table with the provided values.

        :param user: The user of whose behalf the row is created. It might be None if
            the row is created by an anonymous user (i.e. submitting a form).
        :param table: The table for which to create a row for.
        :param values: The values that must be set upon creating the row. The keys must
            be the field ids.
        :param model: If a model is already generated it can be provided here to avoid
            having to generate the model again.
        :param before: If provided the new row will be placed right before that row
            instance.
        :param user_field_names: Whether or not the values are keyed by the internal
            Baserow field name (field_1,field_2 etc) or by the user field names.
        :param values_already_prepared: Whether or not the values are already sanitized
            and validated for every field and can be used directly by the handler
            without any further check.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :raises FieldDataConstraintException: When a field data constraint is violated.
        :return: The created row instance.
        :rtype: Model
        """

        if not values:
            values = {}

        if model is None:
            model = table.get_model()

        if user_field_names:
            values = self.map_user_field_name_dict_to_internal(
                model._field_objects, values
            )

        if not values_already_prepared:
            values_with_defaults = self.prepare_values_with_defaults(
                model._field_objects, [values]
            )
            prepared_values = self.prepare_values(
                model._field_objects, values_with_defaults[0]
            )
        else:
            prepared_values = values

        before_return = before_rows_create.send(
            self, user=user, table=table, model=model
        )

        row_values, manytomany_values = self.extract_manytomany_values(
            prepared_values, model
        )
        row_values["order"] = self.get_unique_orders_before_row(before, model)[0]

        if getattr(model, CREATED_BY_COLUMN_NAME, None):
            row_values[CREATED_BY_COLUMN_NAME] = user if user and user.id else None

        if getattr(model, LAST_MODIFIED_BY_COLUMN_NAME, None):
            row_values[LAST_MODIFIED_BY_COLUMN_NAME] = (
                user if user and user.id else None
            )

        field_rules_handler = FieldRuleHandler(table, user)

        field_rules_handler.on_rows_create([row_values])
        instance = model(**row_values)
        field_rules_handler.validate_row(instance)

        try:
            instance.save(force_insert=True)
            rows_created_counter.add(1)
        except Exception as exc:
            if is_unique_violation_error(exc):
                raise FieldDataConstraintException()
            else:
                raise exc

        m2m_change_tracker = RowM2MChangeTracker()
        for field_name, value in manytomany_values.items():
            m2m_objects, _ = self._prepare_m2m_field_related_objects(
                instance, field_name, value
            )
            field_object = model.get_field_object(field_name)
            m2m_change_tracker.track_m2m_created_for_new_row(
                instance,
                field_object["field"],
                value,
            )
            getattr(instance, field_name).through.objects.bulk_create(m2m_objects)

        cascade_update = field_rules_handler.collector.get_processed_rows()

        fields, dependant_fields = self.update_dependencies_of_rows_created(
            model, [instance]
        )

        self.update_dependencies_of_rows_updated(
            table=table,
            model=model,
            updated_rows=cascade_update.updated_rows,
            updated_field_ids=cascade_update.field_ids,
        )

        if model.fields_requiring_refresh_after_insert():
            instance.refresh_from_db(
                fields=model.fields_requiring_refresh_after_insert()
            )

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(fields + dependant_fields)
        SearchHandler.schedule_update_search_data(
            table, row_ids=[instance.id] + cascade_update.row_ids
        )

        if cascade_update.row_ids:
            updated_rows = list(
                model.objects.all()
                .enhance_by_fields()
                .filter(id__in=list(cascade_update.row_ids))
            )
            cascade_update.updated_rows = updated_rows

        rows_created.send(
            self,
            rows=[instance],
            before=before,
            user=user,
            table=table,
            model=model,
            send_realtime_update=True,
            send_webhook_events=send_webhook_events,
            rows_values_refreshed_from_db=False,
            m2m_change_tracker=m2m_change_tracker,
            fields=fields,
            dependant_fields=dependant_fields,
            before_return=before_return,
        )

        return instance

    # noinspection PyMethodMayBeStatic
    def map_user_field_name_dict_to_internal(
        self,
        field_objects,
        values,
    ):
        """
        Takes the field objects for a model and a dictionary keyed by user specified
        field names for that model. Then will convert the keys from the user names to
        the internal Baserow field names which look like field_1, field_2 and
        correspond to the actual database column names.

        :param field_objects: The field objects for a model.
        :param values: A dictionary keyed by user field names to values.
        :return: A dictionary with the same values but the keys converted to the
            corresponding internal baserow field name (field_1,field_2 etc)
        """

        to_internal_name = {}
        for field_object in field_objects.values():
            to_internal_name[field_object["field"].name] = field_object["name"]

        mapped_back_to_internal_field_names = {}
        for user_field_name, value in values.items():
            internal_name = to_internal_name[user_field_name]
            mapped_back_to_internal_field_names[internal_name] = value
        values = mapped_back_to_internal_field_names
        return values

    def update_row_by_id(
        self,
        user: AbstractUser,
        table: Table,
        row_id: int,
        values: Dict[str, Any],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        values_already_prepared: bool = False,
    ) -> GeneratedTableModelForUpdate:
        """
        Updates one or more values of the provided row_id.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be updated.
        :param row_id: The id of the row that must be updated.
        :param values: The values that must be updated. The keys must be the field ids.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the row is updated in the view.
            This can result in different permissions checks.
        :param values_already_prepared: Whether or not the values are already sanitized
            and validated for every field and can be used directly by the handler
            without any further check.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        :return: The updated row instance.
        """

        if model is None:
            model = table.get_model()

        with transaction.atomic():
            row = self.get_row_for_update(
                user, table, row_id, enhance_by_fields=True, model=model
            )
            return self.update_row(
                user,
                table,
                row,
                values,
                model=model,
                view=view,
                values_already_prepared=values_already_prepared,
            )

    def update_row(
        self,
        user: AbstractUser,
        table: Table,
        row: GeneratedTableModelForUpdate,
        values: Dict[str, Any],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        values_already_prepared: bool = False,
    ) -> GeneratedTableModelForUpdate:
        """
        Updates one or more values of the provided row_id.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be updated.
        :param row: the row that must be updated.
        :param values: The values that must be updated. The keys must be the field ids.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the row is updated in the view.
            This can result in different permissions checks.
        :param values_already_prepared: Whether or not the values are already sanitized
            and validated for every field and can be used directly by the handler
            without any further check.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        :raises FieldDataConstraintException: When a field data constraint is violated.
        :return: The updated row instance.
        """

        self._check_permissions_with_view_fallback(
            UpdateDatabaseRowOperationType.type,
            UpdateViewRowOperationType.type,
            user,
            table,
            view,
            [row.id],
        )

        if model is None:
            model = table.get_model()

        updated_fields_by_name = {}
        updated_fields = []
        updated_field_ids = set()
        for field_id, field in model._field_objects.items():
            if field_id in values or field["name"] in values:
                updated_field_ids.add(field_id)
                updated_fields_by_name[field["name"]] = field["field"]
                updated_fields.append(field["field"])

        self._check_write_fields_values_permissions(user, model, [values])

        rows = [row]
        before_return = before_rows_update.send(
            self,
            rows=rows,
            user=user,
            table=table,
            model=model,
            updated_field_ids=updated_field_ids,
        )

        if not values_already_prepared:
            prepared_values = self.prepare_values(model._field_objects, values)
        else:
            prepared_values = values

        row_values, manytomany_values = self.extract_manytomany_values(
            prepared_values, model
        )
        update_row_fields = []
        for name, value in row_values.items():
            setattr(row, name, value)
            update_row_fields.append(name)

        # This update can remove link row connections with other rows. We need to keep
        # track of these so we can later update any dependant cells in those rows that
        # we used to link to. This is a dictionary where the key is the id link row
        # field in this table, and the value is a set of row ids that this row used to
        # link to via that link row field.
        m2m_change_tracker = RowM2MChangeTracker()

        for name, value in manytomany_values.items():
            field = updated_fields_by_name[name]
            value = [v if not hasattr(v, "id") else v.id for v in value]
            m2m_change_tracker.track_m2m_update_for_field_and_row(
                field, name, row, value
            )
            getattr(row, name).set(value)

        always_updated_fields = ["updated_on"] + [
            fo["field"].db_column for fo in model.get_field_objects_to_always_update()
        ]
        if getattr(model, LAST_MODIFIED_BY_COLUMN_NAME, None):
            setattr(row, LAST_MODIFIED_BY_COLUMN_NAME, user if user.id else None)
            always_updated_fields.append(LAST_MODIFIED_BY_COLUMN_NAME)

        try:
            row.save(update_fields=update_row_fields + always_updated_fields)
        except Exception as exc:
            if is_unique_violation_error(exc):
                raise FieldDataConstraintException()
            else:
                raise exc
        rows_updated_counter.add(1)

        dependant_fields = self.update_dependencies_of_rows_updated(
            table, [row], model, updated_field_ids, m2m_change_tracker
        )
        # We need to refresh here as ExpressionFields might have had their values
        # updated. Django does not support UPDATE .... RETURNING and so we need to
        # query for the rows updated values instead.
        row.refresh_from_db(fields=model.fields_requiring_refresh_after_update())

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(updated_fields + dependant_fields)
        SearchHandler.schedule_update_search_data(
            table,
            fields=[f for f in updated_fields if f.id in updated_field_ids],
            row_ids=[row.id],
        )

        rows_updated.send(
            self,
            rows=rows,
            user=user,
            table=table,
            model=model,
            before_return=before_return,
            updated_field_ids=updated_field_ids,
            m2m_change_tracker=m2m_change_tracker,
            fields=[f for f in updated_fields if f.id in updated_field_ids],
            dependant_fields=dependant_fields,
        )

        return row

    def update_dependencies_of_rows_updated(
        self,
        table: Table,
        updated_rows: List[GeneratedTableModel],
        model: Type[GeneratedTableModel],
        updated_field_ids: Set[int],
        m2m_change_tracker: Optional[RowM2MChangeTracker] = None,
        skip_search_updates: bool = False,
    ) -> List["DjangoField"]:
        """
        Prepares a list of fields that are dependent on the updated fields and updates
        them.

        :param table: The table where the rows are updated.
        :param updated_rows: The rows that are updated.
        :param model: The model of the table.
        :param updated_field_ids: The field ids that are updated.
        :param m2m_change_tracker: The tracker that keeps track of the many to many
            changes.
        :param skip_search_updates: Set to True to skip search updates.
        :return: The dependant fields that are updated.
        """

        field_cache = FieldCache()
        field_cache.cache_model(model)
        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                table.id,
                updated_field_ids,
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=table.database_id,
            )
        )
        deleted_m2m_rels_per_link_field = None
        if m2m_change_tracker is not None:
            deleted_m2m_rels_per_link_field = (
                m2m_change_tracker.get_deleted_link_row_rels_for_update_collector()
            )
        update_collector = FieldUpdateCollector(
            table,
            starting_row_ids=[row.id for row in updated_rows],
            deleted_m2m_rels_per_link_field=deleted_m2m_rels_per_link_field,
        )
        updated_fields = []
        for depth, dependant_fields_group in enumerate(
            all_dependent_fields_grouped_by_depth
        ):
            dependency_context = DependencyContext(depth=depth)
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                updated_fields.append(dependant_field)
                dependant_field_type.row_of_dependency_updated(
                    dependant_field,
                    updated_rows,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                    dependency_context,
                )
            update_collector.apply_updates_and_get_updated_fields(
                field_cache, skip_search_updates
            )
        return updated_fields

    def force_create_rows(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        before_row: Optional[GeneratedTableModel] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        generate_error_report: bool = False,
        skip_search_update: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> CreatedRowsData:
        """
        Creates new rows for a given table without checking permissions. It also calls
        the rows_created signal.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param rows_values: List of rows values for rows that need to be created.
        :param before_row: If provided the new rows will be placed right before the
            before_row.
        :param model: If the correct model has already been generated it can be provided
            so that it does not have to be generated for a second time.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param generate_error_report: When set to True the return
        :param skip_search_update: If you want to instead trigger the search handler
            cells update later on after many create_rows calls then set this to True
            but make sure you trigger it eventually.
        :param signal_params: Additional parameters that are added to the signal.
        :return: The created row instances.

        """

        if model is None:
            model = table.get_model()

        if signal_params is None:
            signal_params = {}

        user_id = user and user.id

        unique_orders = self.get_unique_orders_before_row(
            before_row, model, amount=len(rows_values)
        )

        report = {}
        rows_values_with_defaults = self.prepare_values_with_defaults(
            model._field_objects, rows_values
        )
        prepared_rows_values, errors = self.prepare_rows_in_bulk(
            model._field_objects,
            rows_values_with_defaults,
            generate_error_report=generate_error_report,
        )
        report.update({index: err for index, err in errors.items()})

        before_return = before_rows_create.send(
            self, user=user, table=table, model=model
        )

        field_rules_handler = FieldRuleHandler(table, user)
        field_rules_handler.on_rows_create(prepared_rows_values)

        rows_relationships = []
        for index, row in enumerate(
            prepared_rows_values, start=-len(prepared_rows_values)
        ):
            row_values, manytomany_values = self.extract_manytomany_values(row, model)
            row_values["order"] = unique_orders[index]

            if getattr(model, CREATED_BY_COLUMN_NAME, None):
                row_values[CREATED_BY_COLUMN_NAME] = user if user_id else None

            if getattr(model, LAST_MODIFIED_BY_COLUMN_NAME, None):
                row_values[LAST_MODIFIED_BY_COLUMN_NAME] = user if user_id else None

            instance = model(**row_values)
            field_rules_handler.validate_row(instance)

            relations = {
                field_name: value
                for field_name, value in manytomany_values.items()
                if value and len(value) > 0
            }
            rows_relationships.append((instance, relations))
            # This is a hack to make `BaserowExpressionField.pre_save` (called
            # by bulk_create immediately below) being able to access the
            # relationships values, so the formula can be correctly computed
            # when saving the row, before the many to many relationships are
            # saved.
            instance._m2m_values = relations

        cascade_updated = field_rules_handler.collector.get_processed_rows()

        rows = [row for (row, _) in rows_relationships]

        try:
            with transaction.atomic():
                inserted_rows = model.objects.bulk_create(rows)
        except Exception as exc:
            inserted_rows = []
            if is_unique_violation_error(exc):
                if not generate_error_report:
                    raise FieldDataConstraintException()

                for index, (row, _) in enumerate(rows_relationships):
                    report[index] = {
                        "non_field_errors": [
                            "Row was not inserted due to conflicts or constraints"
                        ]
                    }
            else:
                raise exc

        inserted_rows_count = len(inserted_rows)
        rows_created_counter.add(inserted_rows_count)

        many_to_many = defaultdict(list)
        m2m_change_tracker = RowM2MChangeTracker()

        for index, row in enumerate(inserted_rows):
            _, manytomany_values = rows_relationships[index]
            for field_name, value in manytomany_values.items():
                m2m_objects, _ = self._prepare_m2m_field_related_objects(
                    row, field_name, value
                )
                many_to_many[field_name].extend(m2m_objects)

                field_object = model.get_field_object(field_name)
                m2m_change_tracker.track_m2m_created_for_new_row(
                    row, field_object["field"], value
                )

        for field_name, values in many_to_many.items():
            through = getattr(model, field_name).through
            through.objects.bulk_create(values)

        _, dependant_fields = self.update_dependencies_of_rows_created(
            model,
            inserted_rows,
        )

        from baserow.contrib.database.views.handler import ViewHandler

        updated_fields = [o["field"] for o in model._field_objects.values()]
        updated_field_ids = [f.id for f in updated_fields]

        ViewHandler().field_value_updated(updated_fields + dependant_fields)
        if not skip_search_update:
            SearchHandler.schedule_update_search_data(
                table,
                fields=updated_fields,
                row_ids=[r.id for r in inserted_rows] + list(cascade_updated.row_ids),
            )

        if cascade_updated.row_ids:
            cascade_updated.field_ids.update(updated_field_ids)
            updated_rows = list(
                model.objects.all()
                .enhance_by_fields()
                .filter(id__in=list(cascade_updated.row_ids))
            )
            cascade_updated.updated_rows = updated_rows

        rows_to_return = inserted_rows
        rows_values_refreshed_from_db = False
        if send_realtime_update or send_webhook_events:
            # Since the update collector can automatically update fields of
            # newly created rows without refreshing their values, we pull the
            # values again here to ensure we have the most recent updates.
            rows_to_return = list(
                model.objects.all()
                .enhance_by_fields()
                .filter(id__in=[row.id for row in inserted_rows])
            )
            rows_values_refreshed_from_db = True

        # rows_to_return might be empty if all the values were invalid, so don't
        # send the signal and run callbacks on an empty list.
        if rows_to_return:
            rows_created.send(
                self,
                rows=rows_to_return,
                before=before_row,
                user=user,
                table=table,
                model=model,
                rows_values_refreshed_from_db=rows_values_refreshed_from_db,
                send_realtime_update=send_realtime_update,
                send_webhook_events=send_webhook_events,
                prepared_rows_values=prepared_rows_values,
                m2m_change_tracker=m2m_change_tracker,
                fields=updated_fields,
                dependant_fields=dependant_fields,
                before_return=before_return,
                **signal_params,
            )

        return CreatedRowsData(
            rows_to_return, report, updated_field_ids, cascade_updated
        )

    def create_rows(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        before_row: Optional[GeneratedTableModel] = None,
        view: Optional["View"] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        generate_error_report: bool = False,
        skip_search_update: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> CreatedRowsData:
        """
        Creates new rows for a given table if the user
        belongs to the related workspace. It also calls the rows_created signal.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param rows_values: List of rows values for rows that need to be created.
        :param before_row: If provided the new rows will be placed right before
            the before_row.
        :param view: Optionally provide view, if the rows were created in the view.
            This can result in different permissions checks.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param generate_error_report: When set to True the return
        :param skip_search_update: If you want to instead trigger the search handler
            cells update later on after many create_rows calls then set this to True
            but make sure you trigger it eventually.
        :param signal_params: Additional parameters that are added to the signal.
        :return: The created row instances.

        """

        self._check_permissions_with_view_fallback(
            CreateRowDatabaseTableOperationType.type,
            CreateViewRowOperationType.type,
            user,
            table,
            view,
        )

        if model is None:
            model = table.get_model()

        self._check_write_fields_values_permissions(user, model, rows_values)

        return self.force_create_rows(
            user,
            table,
            rows_values,
            before_row,
            model,
            send_realtime_update,
            send_webhook_events,
            generate_error_report,
            skip_search_update,
            signal_params=signal_params,
        )

    def update_dependencies_of_rows_created(
        self,
        model: Type[GeneratedTableModel],
        created_rows: List[GeneratedTableModel],
    ) -> List["DjangoField"]:
        """
        Generates a list of dependant fields that need to be updated after the rows have
        been created and updates them.

        :param model: The model of the table.
        :param rows: The rows that have been created.
        :return: The dependant fields that are updated.
        """

        row_ids = [row.id for row in created_rows]
        table = model.baserow_table
        update_collector = FieldUpdateCollector(table, starting_row_ids=row_ids)

        field_cache = FieldCache()
        field_cache.cache_model(model)
        field_ids = []
        fields = []
        for field_object in model._field_objects.values():
            field_type = field_object["type"]
            field = field_object["field"]
            field_ids.append(field.id)
            fields.append(field)

            field_type.after_rows_created(
                field, created_rows, update_collector, field_cache
            )
        update_collector.apply_updates_and_get_updated_fields(field_cache)

        dependant_fields = []
        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                table.id,
                field_ids,
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=table.database_id,
            )
        )

        for depth, dependant_fields_group in enumerate(
            all_dependent_fields_grouped_by_depth
        ):
            dependency_context = DependencyContext(depth=depth)
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependant_fields_group:
                dependant_fields.append(dependant_field)

                dependant_field_type.row_of_dependency_created(
                    dependant_field,
                    created_rows,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                    dependency_context,
                )
            update_collector.apply_updates_and_get_updated_fields(field_cache)
        return fields, dependant_fields

    def _prepare_m2m_field_related_objects(
        self, row: GeneratedTableModel, field_name: str, value: List[Any]
    ) -> Tuple[List[Type[Model]], Tuple[str, str]]:
        """
        Prepares the many to many related objects for a given row and field name, taking
        into account whether the field is self-referencing or not.

        :param row: The row instance for which the related objects must be prepared.
        :param field_name: The name of the field for which the related objects must be
            prepared.
        :param value: The value of the field.
        :return: A list of related objects and a tuple containing a string indicating
            the column name of the row in the through table and a string indicating the
            column name of the value in the through table.
        """

        model = row._meta.model
        through = getattr(model, field_name).through
        through_fields = through._meta.get_fields()
        value_column = None
        row_column = None

        model_field = model._meta.get_field(field_name)
        is_referencing_the_same_table = model_field.model == model_field.related_model

        # Figure out which field in the many to many through table holds the row
        # value and which one contains the value.
        for field in through_fields:
            if type(field) is not ForeignKey:
                continue

            if is_referencing_the_same_table:
                # django creates 'from_tableXmodel' and 'to_tableXmodel'
                # columns for self-referencing many_to_many relations.
                row_column = field.get_attname_column()[1]
                value_column = row_column.replace("from", "to")
                break
            elif field.remote_field.model == model:
                row_column = field.get_attname_column()[1]
            else:
                value_column = field.get_attname_column()[1]

        m2m_objects = [
            through(
                **{
                    row_column: row.id,
                    value_column: v.id if hasattr(v, "id") else v,
                }
            )
            for v in value
        ]

        return m2m_objects, (row_column, value_column)

    def validate_rows(
        self,
        table: Table,
        rows: List[Dict[str, Any]],
        progress: Optional[Progress] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validates rows by batch and generates an error report.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param rows: List of rows values for rows that need to be created.
        :param progress: Give a progress instance to track the progress of the import.
        :return: The error report.
        """

        from baserow.api.exceptions import RequestBodyValidationException
        from baserow.api.utils import validate_data
        from baserow.contrib.database.api.rows.serializers import (
            get_row_serializer_class,
        )

        if not rows:
            return {}

        if progress:
            progress.increment(state=ROW_IMPORT_VALIDATION)

        model = table.get_model()
        # Use serializer to validate incoming data
        validation_serializer = get_row_serializer_class(model)
        report = {}
        for count, chunk in enumerate(grouper(BATCH_SIZE, rows)):
            row_start_index = count * BATCH_SIZE
            try:
                validate_data(validation_serializer, list(chunk), many=True)
            except RequestBodyValidationException as e:
                for index, err in enumerate(e.detail["detail"]):
                    report[row_start_index + index] = err

            if progress:
                progress.increment(len(chunk))

        return report

    def force_create_rows_by_batch(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        progress: Optional[Progress] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        signal_params: Optional[Dict] = None,
    ) -> Tuple[List[GeneratedTableModel], Dict[str, Dict[str, Any]]]:
        """
        Creates rows by batch and generates an error report instead of failing on first
        error.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param rows_values: List of rows values for rows that need to be created.
        :param progress: Give a progress instance to track the progress of the import.
        :param model: Optional model to prevent recomputing table model.
        :return: The created rows and the error report.
        """

        if not rows_values:
            return [], {}

        if progress:
            progress.increment(state=ROW_IMPORT_CREATION)

        if model is None:
            model = table.get_model()

        report = {}
        all_created_rows = []
        for count, chunk in enumerate(grouper(BATCH_SIZE, rows_values)):
            row_start_index = count * BATCH_SIZE
            (
                created_rows,
                creation_report,
                field_ids,
                cascade_update,
            ) = self.force_create_rows(
                user=user,
                table=table,
                model=model,
                rows_values=chunk,
                generate_error_report=True,
                send_realtime_update=False,
                send_webhook_events=False,
                # Don't trigger loads of search updates for every batch of rows we
                # create but instead a single one for this entire table at the end.
                skip_search_update=True,
                signal_params=signal_params,
            )

            for valid_index, field_errors in creation_report.items():
                report[int(valid_index) + row_start_index] = prepare_field_errors(
                    field_errors
                )

            if progress:
                progress.increment(len(chunk))

            all_created_rows += created_rows

        SearchHandler.schedule_update_search_data(
            table, row_ids=[r.id for r in all_created_rows]
        )

        return all_created_rows, report

    def force_update_rows_by_batch(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        progress: Progress,
        model: Optional[Type[GeneratedTableModel]] = None,
        signal_params: Optional[Dict] = None,
    ) -> Tuple[List[Dict[str, Any] | None], Dict[str, Dict[str, Any]]]:
        """
        Updates rows by batch and generates an error report instead of failing on first
        error. If bulk update fails, falls back to individual row updates.

        :param user: The user of whose behalf the rows are updated.
        :param table: The table for which the rows should be updated.
        :param rows_values: List of rows values for rows that need to be updated.
        :param progress: Give a progress instance to track the progress of the import.
        :param model: Optional model to prevent recomputing table model.
        :param signal_params: Additional parameters that are added to the signal.
        :return: The updated rows and the error report.
        """

        if not rows_values:
            return [], {}

        if signal_params is None:
            signal_params = {}

        progress.increment(state=ROW_IMPORT_CREATION)

        if model is None:
            model = table.get_model()

        report = {}
        all_updated_rows = []
        for count, chunk in enumerate(grouper(BATCH_SIZE, rows_values)):
            row_start_index = count * BATCH_SIZE

            try:
                with transaction.atomic():
                    result = self.force_update_rows(
                        user=user,
                        table=table,
                        model=model,
                        rows_values=chunk,
                        send_realtime_update=False,
                        send_webhook_events=False,
                        generate_error_report=True,
                        signal_params=signal_params,
                    )
                    report.update(result.errors)
                    all_updated_rows.extend(result.updated_rows)
            except Exception as exc:
                if is_unique_violation_error(exc):
                    for index, _ in enumerate(chunk):
                        report[row_start_index + index] = {
                            "non_field_errors": [
                                "Row was not updated due to conflicts or constraints"
                            ]
                        }
                else:
                    raise exc

            if progress:
                progress.increment(len(chunk))

        return all_updated_rows, report

    def import_rows(
        self,
        user: AbstractUser,
        table: Table,
        data: list[list[Any]],
        configuration: FileImportConfiguration | None = None,
        validate: bool = True,
        progress: Optional[Progress] = None,
        send_realtime_update: bool = True,
    ) -> Tuple[List[GeneratedTableModel], Dict[str, Dict[str, Any]]]:
        """
        Creates new rows for a given table if the user belongs to the related
        workspace. It also calls the rows_created passing the
        send_realtime_update parameter. The data are validated before the
        creation if validate is True. when a row fails to import, it doesn't
        stop the import. Instead an error report is created with the raised
        error for each field of each failing rows.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param data: List of rows values for rows that need to be created.
        :param configuration: Optional import configuration dict.
        :param validate: If True the data are validated before the import.
        :param progress: Give a progress instance to track the progress of the
            import.
        :param send_realtime_update: The parameter passed to the rows_created
            signal indicating if a realtime update should be send.

        :raises InvalidRowLength:

        :return: The created row instances and the error report.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user,
            ImportRowsDatabaseTableOperationType.type,
            workspace=workspace,
            context=table,
        )
        model = table.get_model()

        error_report = RowErrorReport(data)
        configuration = configuration or {}
        update_handler = UpsertRowsMappingHandler(
            table=table,
            upsert_fields=configuration.get("upsert_fields") or [],
            upsert_values=configuration.get("upsert_values") or [],
        )
        # Pre-run upsert configuration validation.
        # Can raise InvalidRowLength
        update_handler.validate()

        skipped_field_ids = configuration.get("skipped_fields", []) or []
        try:
            skipped_fields = [
                model.get_field_object_by_id(field_id)["field"]
                for field_id in skipped_field_ids
            ]
        except ValueError:
            raise FieldNotInTable("The field ID is not found in the table.")

        fields = [
            field_object["field"]
            for field_object in model._field_objects.values()
            if not field_object["type"].read_only
            and not field_object["field"].read_only
        ]

        # Sort by primary first (descending), then by order, then by id
        fields.sort(key=lambda f: (not f.primary, f.order, f.id))

        for index, row in enumerate(data):
            # Check row length
            if len(row) > len(fields):
                error_report.add_error(
                    index,
                    {"non_field_errors": ["Too many values in this line."]},
                )
            else:
                new_row = list(row)
                # Fill incomplete rows with empty values
                new_row.extend([None] * (len(fields) - len(row)))

                # Reshape data by field as expected by the import
                error_report.update_row(
                    index,
                    {
                        f"field_{fields[index].id}": value
                        for index, value in enumerate(new_row)
                    },
                )

        # STEP 1: pre-validate data with serializer
        if validate:
            (
                valid_rows,
                original_row_index_mapping,
            ) = error_report.get_valid_rows_and_mapping()

            validation_sub_progress = (
                progress.create_child(50, len(valid_rows)) if progress else None
            )

            validation_report = self.validate_rows(
                table, valid_rows, progress=validation_sub_progress
            )

            for index, error in validation_report.items():
                error_report.add_error(original_row_index_mapping[int(index)], error)

        (
            valid_rows,
            original_row_index_mapping,
        ) = error_report.get_valid_rows_and_mapping()

        # STEP 2: create rows in DB
        creation_sub_progress = (
            progress.create_child(50 if validate else 100, len(valid_rows))
            if progress
            else None
        )

        # Make sure to exclude fields that cannot be written by the user.
        # NOTE: all rows contain the same fields, so we can just check the first one
        unwritable_fields = self._check_write_fields_values_permissions(
            user, model, valid_rows[:1], raise_if_not_permitted=False
        )
        unwritable_field_names = set(f.db_column for f in unwritable_fields)
        valid_rows = [
            {k: v for k, v in row.items() if k not in unwritable_field_names}
            for row in valid_rows
        ]

        # split rows to insert and update lists. If there's no upsert field selected,
        # this will not populate rows_values_to_update.
        update_map = update_handler.process_map

        rows_values_to_create = []
        rows_values_to_update = []
        if update_map:
            skipped_field_names = set()

            if skipped_fields:
                skipped_field_names = {field.db_column for field in skipped_fields}

            for current_idx, import_idx in original_row_index_mapping.items():
                row = valid_rows[current_idx]
                if update_idx := update_map.get(import_idx):
                    # For upsert operations, filter out skipped fields that were
                    # explicitly marked to be ignored during import. This ensures
                    # that existing values in those fields are preserved in the
                    # database rather than being overwritten.
                    filtered_row = {
                        k: v for k, v in row.items() if k not in skipped_field_names
                    }
                    filtered_row["id"] = update_idx
                    rows_values_to_update.append(filtered_row)
                else:
                    rows_values_to_create.append(row)
        else:
            rows_values_to_create = valid_rows

        created_rows, creation_report = self.force_create_rows_by_batch(
            user,
            table,
            rows_values_to_create,
            progress=creation_sub_progress,
            model=model,
        )

        if rows_values_to_update:
            updated_rows, updated_report = self.force_update_rows_by_batch(
                user,
                table,
                rows_values_to_update,
                progress=creation_sub_progress,
                model=model,
            )

        # Add errors to global report
        for index, error in creation_report.items():
            error_report.add_error(
                original_row_index_mapping[int(index)],
                error,
            )

        if rows_values_to_update:
            for index, error in updated_report.items():
                error_report.add_error(
                    original_row_index_mapping[int(index)],
                    error,
                )

        if send_realtime_update:
            # Just send a single table_updated here as realtime update instead
            # of rows_created because we might import a lot of rows.
            table_updated.send(self, table=table, user=user, force_table_refresh=True)

        return created_rows, error_report.to_dict()

    def get_fields_metadata_for_row_history(
        self,
        row: GeneratedTableModelForUpdate,
        updated_fields: List["DjangoField"],
        metadata,
    ) -> FieldsMetadata:
        """
        Serializes the metadata for the fields that have changed for a given
        row. This method is useful for row_history to be able
        to reconstruct the row fields values as they were before.
        """

        fields_metadata = metadata or {}
        for field in updated_fields:
            if hasattr(row, field.db_column):
                field_type = field_type_registry.get_by_model(field)
                field_metadata = field_type.serialize_metadata_for_row_history(
                    field, row, fields_metadata.get(f"field_{field.id}", None)
                )
                fields_metadata[f"field_{field.id}"] = field_metadata
        return {"id": row.id, **fields_metadata}

    def get_fields_metadata_for_rows(
        self,
        rows: List[GeneratedTableModelForUpdate],
        updated_fields: List["DjangoField"],
        fields_metadata_by_row_id=None,
    ) -> Dict[RowId, FieldsMetadata]:
        """
        For each row, return a dictionary containing the metadata of the
        modified fields, allowing the modified value to be
        reconstructed later.
        """

        rows_by_id = {row.id: row for row in rows}

        if fields_metadata_by_row_id is None:
            fields_metadata_by_row_id: Dict[RowId, FieldsMetadata] = {}
        else:
            fields_metadata_by_row_id = deepcopy(fields_metadata_by_row_id)

        for row_id, original_row in rows_by_id.items():
            fields_metadata = self.get_fields_metadata_for_row_history(
                original_row,
                updated_fields,
                fields_metadata_by_row_id.get(row_id, None),
            )
            fields_metadata_by_row_id[row_id] = fields_metadata

        return fields_metadata_by_row_id

    def _check_write_fields_values_permissions(
        self,
        user: AbstractUser,
        model: GeneratedTableModel,
        rows_values: List[Dict[str, Any]],
        raise_if_not_permitted: bool = True,
    ) -> List["Field"]:
        """
        Verifies if the user has permission to write the values of the fields
        provided in the rows_values. If the user does not have permission,
        a PermissionDenied exception is raised.

        :param user: The user to check permissions for.
        :param model: The model containing the fields.
        :param rows_values: The rows values to check permissions for.
        :return: If raise_if_not_permitted is False, returns the list of fields
            that the user does not have permission to write.
        :raises PermissionDenied: If the user does not have permission to write
            the values of the specified fields.
        """

        field_ids = self._extract_field_ids_from_row_values(rows_values, model)

        fields = [
            fo["field"]
            for fo in model.get_field_objects(include_trash=True)
            if fo["field"].id in field_ids
        ]
        table = model.baserow_table
        perm_checks = [
            PermissionCheck(user, WriteFieldValuesOperationType.type, field)
            for field in fields
        ]
        results = CoreHandler().check_multiple_permissions(
            perm_checks, table.database.workspace
        )
        unwritable_fields = [
            c.context for (c, has_permissions) in results.items() if not has_permissions
        ]
        if unwritable_fields and raise_if_not_permitted:
            raise PermissionDenied(
                f"You don't have permission to update the following fields: {', '.join([f.name for f in unwritable_fields])}"
            )
        return unwritable_fields

    def force_update_rows(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        model: Optional[Type[GeneratedTableModel]] = None,
        rows_to_update: Optional[RowsForUpdate] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        skip_search_update: bool = False,
        generate_error_report: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> UpdatedRowsData:
        """
        Updates field values in batch based on provided rows with the new
        values.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be updated.
        :param rows_values: The list of rows with new values that should be set.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param rows_to_update: If the rows to update have already been generated
            it can be provided so that it does not have to be generated for a
            second time.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param skip_search_update: If you want to instead trigger the search handler
            cells update later on after many create_rows calls then set this to True
            but make sure you trigger it eventually.
        :param generate_error_report: Generate error report if set to True.
        :param signal_params: Additional parameters that are added to the signal.
        :raises RowIdsNotUnique: When trying to update the same row multiple
            times.
        :raises RowDoesNotExist: When any of the rows don't exist.
        :raises FieldDataConstraintException: When a field data constraint is violated.
        :return: An UpdatedRow named tuple containing the updated rows
            instances, the original row values and the updated fields metadata.
        """

        if signal_params is None:
            signal_params = {}

        if model is None:
            model = table.get_model()

        user_id = user and user.id

        prepared_rows_values, errors = self.prepare_rows_in_bulk(
            model._field_objects,
            rows_values,
            generate_error_report=generate_error_report,
        )
        report = {index: err for index, err in errors.items()}
        row_ids = [r["id"] for r in prepared_rows_values]

        non_unique_ids = get_non_unique_values(row_ids)
        if len(non_unique_ids) > 0:
            raise RowIdsNotUnique(non_unique_ids)

        prepared_rows_values_by_id = {}
        for prepared_row_values in prepared_rows_values:
            row_id = prepared_row_values.pop("id")
            prepared_rows_values_by_id[row_id] = prepared_row_values

        if rows_to_update is None:
            rows_to_update = self.get_rows_for_update(model, row_ids)

        if len(rows_to_update) != len(prepared_rows_values):
            db_rows_ids = [db_row.id for db_row in rows_to_update]
            raise RowDoesNotExist(sorted(list(set(row_ids) - set(db_rows_ids))))

        updated_fields = [o["field"] for o in model._field_objects.values()]
        fields_metadata_by_row_id = self.get_fields_metadata_for_rows(
            rows_to_update, updated_fields, None
        )

        updated_field_ids = set()
        field_name_to_field = dict()
        for obj in rows_to_update:
            row_values = prepared_rows_values_by_id[obj.id]
            for field_id, field_obj in model._field_objects.items():
                field_name_to_field[field_obj["name"]] = field_obj["field"]
                if field_id in row_values or field_obj["name"] in row_values:
                    updated_field_ids.add(field_id)

        original_row_values_by_id = {}
        for row in rows_to_update:
            values = self.get_internal_values_for_fields(row, updated_field_ids)
            values["id"] = row.id
            original_row_values_by_id[row.id] = values

        before_return = before_rows_update.send(
            self,
            rows=list(rows_to_update),
            user=user,
            table=table,
            model=model,
            updated_field_ids=updated_field_ids,
            updated_rows_values=prepared_rows_values_by_id,
        )

        from baserow.contrib.database.field_rules.handlers import FieldRuleHandler

        field_rules_handler = FieldRuleHandler(table, user)
        field_rules_handler.on_rows_updated(rows_to_update, prepared_rows_values_by_id)

        field_objects_to_always_update = model.get_field_objects_to_always_update()
        rows_relationships = []
        for obj in rows_to_update:
            # The `updated_on` field is not updated with `bulk_update`, so we manually
            # set the value here.
            obj.updated_on = model._meta.get_field("updated_on").pre_save(
                obj, add=False
            )
            # Add "always update" fields like last_modified or last modified by fields
            # to the updated fields list so that formulas referencing them will
            # be updated correctly.
            for field_object in field_objects_to_always_update:
                updated_field_ids.add(field_object["field"].id)

            prepared_values = prepared_rows_values_by_id[obj.id]
            row_values, manytomany_values = self.extract_manytomany_values(
                prepared_values, model
            )

            for name, value in row_values.items():
                setattr(obj, name, value)

            if getattr(model, LAST_MODIFIED_BY_COLUMN_NAME, None):
                setattr(obj, LAST_MODIFIED_BY_COLUMN_NAME, user if user_id else None)

            relations = {
                field_name: value
                for field_name, value in manytomany_values.items()
                if value or isinstance(value, list)
            }
            rows_relationships.append(relations)
            # This is a hack to make `BaserowExpressionField.pre_save` (called
            # immediately below here) being able to access the relationships
            # values, so the formula can be correctly computed when saving the
            # row, before the many to many relationships are saved.
            obj._m2m_values = relations

            fields_with_pre_save = model.fields_requiring_refresh_after_update()
            for field_name in fields_with_pre_save:
                setattr(
                    obj,
                    field_name,
                    model._meta.get_field(field_name).pre_save(obj, add=False),
                )

            field_rules_handler.validate_row(obj)

        m2m_values_to_add = defaultdict(list)
        m2m_values_to_delete = {}
        row_column_names: Dict[str, str] = {}
        row_ids_change_m2m_per_field = defaultdict(set)

        # This update can remove link row connections with other rows. We need to keep
        # track of these so we can later update any dependant cells in those rows that
        # we used to link to. This is a dictionary where the key is the id link row
        # field in this table, and the value is a set of row ids that these rows used to
        # link to via that link row field.
        m2m_change_tracker = RowM2MChangeTracker()

        for index, row in enumerate(rows_to_update):
            manytomany_values = rows_relationships[index]
            for field_name, value in manytomany_values.items():
                row_ids_change_m2m_per_field[field_name].add(row.id)

                # If this m2m field is a link row we need to find out all connections
                # which will be removed by this update. This is so we can update
                # rows which previously were connected to an updated row, but no
                # longer are.
                field_obj = field_name_to_field[field_name]
                m2m_change_tracker.track_m2m_update_for_field_and_row(
                    field_obj, field_name, row, value
                )

                original_set_of_values = set(
                    original_row_values_by_id[row.id].get(field_name) or []
                )
                # if a list of models is provided as value, make sure to compare the ids
                value_ids = [v.id if hasattr(v, "id") else v for v in value]
                new_set_of_values = set(value_ids)
                to_add = new_set_of_values - original_set_of_values
                to_delete = original_set_of_values - new_set_of_values

                m2m_to_add, (
                    row_column_name,
                    value_column,
                ) = self._prepare_m2m_field_related_objects(
                    row, field_name, list(filter(lambda v: v in to_add, value_ids))
                )
                row_column_names[field_name] = row_column_name

                if len(to_add) > 0:
                    m2m_values_to_add[field_name].extend(m2m_to_add)

                if len(to_delete) > 0:
                    prev_q = m2m_values_to_delete.get(field_name, Q())
                    q_kwargs = {row_column_name: row.id}
                    # Delete all the row relations only if the new value is empty
                    if value_ids:
                        q_kwargs[f"{value_column}__in"] = to_delete
                    m2m_values_to_delete[field_name] = prev_q | Q(**q_kwargs)

        # The many to many relations need to be updated first because they need to
        # exist when the rows are updated in bulk. Otherwise, the formula and lookup
        # fields can't see the relations.
        for field_name, q_filters in m2m_values_to_delete.items():
            through = getattr(model, field_name).through
            delete_qs = through.objects.all().filter(q_filters)
            delete_qs._raw_delete(using=router.db_for_write(delete_qs.model))

        for field_name, m2m_to_add in m2m_values_to_add.items():
            through = getattr(model, field_name).through
            row_column_name = row_column_names[field_name]
            through.objects.bulk_create(m2m_to_add)

        bulk_update_fields = ["updated_on"]
        if field_rules_handler.has_field_rules():
            bulk_update_fields.append(FieldRuleHandler.STATE_COLUMN_NAME)
        updated_field_ids.update(
            field_rules_handler.collector.starting_rows_updated_field_ids
        )

        # Add always update fields to update also fields that are trashed
        for field_object in field_objects_to_always_update:
            bulk_update_fields.append(field_object["name"])

        if getattr(model, LAST_MODIFIED_BY_COLUMN_NAME, None):
            bulk_update_fields.append(LAST_MODIFIED_BY_COLUMN_NAME)

        for field_obj in model._field_objects.values():
            field_id = field_obj["field"].id
            field_name = field_obj["name"]
            field_type = field_obj["type"]
            model_field = model._meta.get_field(field_name)
            if (
                not isinstance(model_field, ManyToManyField)
                and field_id in updated_field_ids
                and field_type.valid_for_bulk_update(field_obj["field"])
            ):
                bulk_update_fields.append(field_name)

        if len(bulk_update_fields) > 0:
            try:
                model.objects.bulk_update(
                    rows_to_update, bulk_update_fields, batch_size=2000
                )
            except Exception as exc:
                if is_unique_violation_error(exc):
                    if generate_error_report:
                        for idx, row in enumerate(rows_to_update):
                            report[idx] = {
                                "non_field_errors": [
                                    "Row was not updated due to conflicts or constraints"
                                ]
                            }
                        return UpdatedRowsData(
                            [],
                            [],
                            original_row_values_by_id,
                            fields_metadata_by_row_id,
                            report,
                            [],
                        )
                    raise FieldDataConstraintException()
                else:
                    raise exc

            rows_updated_counter.add(len(rows_to_update))

        cascade_updated = field_rules_handler.collector.get_processed_rows()

        cascade_fields = [
            f.db_column for f in model.get_fields() if f.id in cascade_updated.field_ids
        ]

        if cascade_updated.updated_rows:
            model.objects.bulk_update(cascade_updated.updated_rows, cascade_fields)

        dependant_fields = self.update_dependencies_of_rows_updated(
            table,
            list(rows_to_update) + cascade_updated.updated_rows,
            model,
            updated_field_ids.union(cascade_updated.field_ids),
            m2m_change_tracker,
        )

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(updated_fields + dependant_fields)
        if not skip_search_update:
            SearchHandler.schedule_update_search_data(
                table,
                fields=[f for f in updated_fields if f.id in updated_field_ids],
                row_ids=row_ids + list(cascade_updated.row_ids),
            )

        # Reload rows from the database to get the updated values for formulas
        updated_rows_to_return = []
        cascade_updated_rows = []

        for row in (
            model.objects.all()
            .enhance_by_fields()
            .filter(id__in=list(set(chain(row_ids, cascade_updated.row_ids))))
        ):
            if row.id in row_ids:
                updated_rows_to_return.append(row)
            if row.id in cascade_updated.row_ids:
                cascade_updated_rows.append(row)

        if cascade_updated.updated_rows:
            cascade_updated.field_ids.update(updated_field_ids)

            # replace updated rows with fresh versions with formula values
            cascade_updated.updated_rows = cascade_updated_rows

        rows_updated.send(
            self,
            rows=updated_rows_to_return,
            user=user,
            table=table,
            model=model,
            before_return=before_return,
            updated_field_ids=updated_field_ids,
            m2m_change_tracker=m2m_change_tracker,
            send_realtime_update=send_realtime_update,
            send_webhook_events=send_webhook_events,
            fields=[f for f in updated_fields if f.id in updated_field_ids],
            dependant_fields=dependant_fields,
            cascade_update=cascade_updated,
            **signal_params,
        )

        fields_metadata_by_row_id = self.get_fields_metadata_for_rows(
            updated_rows_to_return, updated_fields, fields_metadata_by_row_id
        )

        updated_rows_values = [
            {
                "id": updated_row.id,
                **self.get_internal_values_for_fields(updated_row, updated_field_ids),
            }
            # split updated rows from cascade update rows
            for updated_row in updated_rows_to_return
            if updated_row.id in row_ids
        ]
        updated_rows = UpdatedRowsData(
            updated_rows_to_return,
            updated_rows_values,
            original_row_values_by_id,
            fields_metadata_by_row_id,
            report,
            updated_field_ids.union(cascade_updated.field_ids),
            cascade_update=cascade_updated,
        )

        return updated_rows

    def update_rows(
        self,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        rows_to_update: Optional[RowsForUpdate] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        skip_search_update: bool = False,
        generate_error_report: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> UpdatedRowsData:
        """
        Updates field values in batch based on provided rows with the new
        values.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be updated.
        :param rows_values: The list of rows with new values that should be set.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the rows were updated in the view.
            This can result in different permissions checks.
        :param rows_to_update: If the rows to update have already been generated
            it can be provided so that it does not have to be generated for a
            second time.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param skip_search_update: If you want to instead trigger the search handler
            cells update later on after many create_rows calls then set this to True
            but make sure you trigger it eventually.'
        :param generate_error_report: @TODO
        :param signal_params: Additional parameters that are added to the signal.
        :raises RowIdsNotUnique: When trying to update the same row multiple
            times.
        :raises RowDoesNotExist: When any of the rows don't exist.
        :return: An UpdatedRow named tuple containing the updated rows
            instances, the original row values and the updated fields metadata.
        """

        self._check_permissions_with_view_fallback(
            UpdateDatabaseRowOperationType.type,
            UpdateViewRowOperationType.type,
            user,
            table,
            view,
            [row["id"] for row in rows_values],
        )

        if model is None:
            model = table.get_model()

        self._check_write_fields_values_permissions(user, model, rows_values)

        return self.force_update_rows(
            user,
            table,
            rows_values,
            model,
            rows_to_update,
            send_realtime_update,
            send_webhook_events,
            skip_search_update,
            generate_error_report=generate_error_report,
            signal_params=signal_params,
        )

    def _extract_field_ids_from_row_values(
        self, rows_values: List[Dict[str, Any]], model: GeneratedTableModel
    ) -> Set[int]:
        """
        Extracts the field ids that are updated based on the provided rows
        values. This is used to determine which fields need to be updated
        and verified for permissions.

        :param rows_values: The list of rows values to check.
        :param model: The model that should be used to get the field ids.
        :return: A set of field ids that are updated.
        """

        model_field_ids = set([field_id for field_id in model._field_objects.keys()])

        updated_field_ids = set()
        for row in rows_values:
            row_keys = self.extract_field_ids_from_dict(row)
            row_field_ids = set(row_keys) & model_field_ids
            updated_field_ids |= row_field_ids

        return updated_field_ids

    def get_rows(
        self, model: GeneratedTableModel, row_ids: List[int]
    ) -> QuerySet[GeneratedTableModel]:
        """
        Returns a list of rows based on the provided row ids.

        :param model: The model that should be used to get the rows.
        :param row_ids: The list of row ids that should be fetched.
        :return: A queryset of the fetched rows.
        """

        return model.objects.filter(id__in=row_ids).enhance_by_fields()

    def get_rows_for_update(
        self, model: GeneratedTableModel, row_ids: List[int]
    ) -> RowsForUpdate:
        """
        Get the rows to update. This method doesn't guarantee that the rows
        exist or are returned in the same order as the row_ids (as the default
        table ordering is by [order, id]).
        """

        return cast(
            RowsForUpdate, self.get_rows(model, row_ids).select_for_update(of=("self",))
        )

    def move_row_by_id(
        self,
        user: AbstractUser,
        table: Table,
        row_id: int,
        before_row: Optional[GeneratedTableModel] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
    ) -> GeneratedTableModelForUpdate:
        """
        Updates the row order value.

        :param user: The user of whose behalf the row is moved
        :param table: The table that contains the row that needs to be moved.
        :param row_id: The row id that needs to be moved.
        :param before_row: If provided the new row will be placed right before that row
            instance. Otherwise the row will be moved to the end.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        """

        if model is None:
            model = table.get_model()

        with transaction.atomic():
            row = self.get_row_for_update(user, table, row_id, model=model)
            return self.move_row(user, table, row, before_row=before_row, model=model)

    def move_row(
        self,
        user: AbstractUser,
        table: Table,
        row: GeneratedTableModelForUpdate,
        before_row: Optional[GeneratedTableModel] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModelForUpdate:
        """
        Updates the row order value.

        :param user: The user of whose behalf the row is moved
        :param table: The table that contains the row that needs to be moved.
        :param row: The row that needs to be moved.
        :param before_row: If provided the new row will be placed right before that row
            instance. Otherwise the row will be moved to the end.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user,
            MoveRowDatabaseRowOperationType.type,
            workspace=workspace,
            context=table,
        )

        if model is None:
            model = table.get_model()

        before_return = before_rows_update.send(
            self, rows=[row], user=user, table=table, model=model, updated_field_ids=[]
        )

        row.order = self.get_unique_orders_before_row(before_row, model)[0]
        row.save(update_fields=["order", "updated_on"])

        # All fields must be marked as updated because the lookup fields can depend
        # on the row order. Only fields that are specifically marked as
        # `not include_in_row_move_updated_fields` are excluded. This is for example
        # the case with the formula because that value can depend on other values and
        # must be updated in the right grouped order in
        # `update_dependencies_of_rows_updated`.
        updated_field_ids = []
        updated_fields = []
        for field_id, field_object in model._field_objects.items():
            if field_object["type"].include_in_row_move_updated_fields:
                updated_field_ids.append(field_id)
                field = field_object["field"]
                updated_fields.append(field)

        dependant_fields = self.update_dependencies_of_rows_updated(
            table, [row], model, updated_field_ids
        )

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(updated_fields + dependant_fields)

        rows_updated.send(
            self,
            rows=[row],
            user=user,
            table=table,
            model=model,
            before_return=before_return,
            updated_field_ids=[],
            prepared_rows_values=None,
            send_webhook_events=send_webhook_events,
            fields=[],
            dependant_fields=dependant_fields,
        )

        return row

    def delete_row_by_id(
        self,
        user: AbstractUser,
        table: Table,
        row_id: int,
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModel:
        """
        Deletes an existing row of the given table and with row_id.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row_id: The id of the row that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_deleted or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :returns GeneratedTableModel: removed row
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        """

        if model is None:
            model = table.get_model()

        with transaction.atomic():
            row = self.get_row(user, table, row_id, model=model, view=view)
            self.delete_row(
                user,
                table,
                row,
                model=model,
                view=view,
                send_realtime_update=send_realtime_update,
                send_webhook_events=send_webhook_events,
            )
        return row

    def delete_row(
        self,
        user: AbstractUser,
        table: Table,
        row: GeneratedTableModelForUpdate,
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModelForUpdate:
        """
        Deletes an existing row of the given table and with row_id.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row: The row that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the rows is deleted in the view.
            This can result in different permissions checks.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_deleted or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :returns GeneratedTableModelForUpdate: removed row
        """

        self._check_permissions_with_view_fallback(
            DeleteDatabaseRowOperationType.type,
            DeleteViewRowOperationType.type,
            user,
            table,
            view,
            [row.id],
        )

        if model is None:
            model = table.get_model()

        before_return = before_rows_delete.send(
            self, rows=[row], user=user, table=table, model=model
        )

        workspace = table.database.workspace
        TrashHandler.trash(user, workspace, table.database, row)
        rows_deleted_counter.add(1)

        (
            updated_fields,
            dependant_fields,
        ) = self.update_dependencies_of_rows_deleted(table, row, model)

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(updated_fields + dependant_fields)

        rows_deleted.send(
            self,
            rows=[row],
            user=user,
            table=table,
            model=model,
            before_return=before_return,
            send_realtime_update=send_realtime_update,
            send_webhook_events=send_webhook_events,
            fields=updated_fields,
            dependant_fields=dependant_fields,
        )
        return row

    def update_dependencies_of_rows_deleted(self, table, row, model):
        update_collector = FieldUpdateCollector(table, starting_row_ids=[row.id])
        field_cache = FieldCache()
        field_cache.cache_model(model)
        updated_field_ids = []
        updated_fields = []

        for field_id, field_object in model._field_objects.items():
            updated_field_ids.append(field_id)
            field = field_object["field"]
            updated_fields.append(field)

        dependant_fields = []

        # Get dependent fields grouped by their dependency level to ensure
        # correct update order
        all_dependent_fields_grouped_by_level = (
            FieldDependencyHandler.group_all_dependent_fields_by_level(
                table.id,
                updated_field_ids,
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=table.database_id,
            )
        )

        for depth, dependent_fields_level in enumerate(
            all_dependent_fields_grouped_by_level
        ):
            dependency_context = DependencyContext(depth=depth)
            for (
                dependant_field,
                dependant_field_type,
                path_to_starting_table,
            ) in dependent_fields_level:
                dependant_fields.append(dependant_field)

                dependant_field_type.row_of_dependency_deleted(
                    dependant_field,
                    row,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                    dependency_context,
                )

            update_collector.apply_updates_and_get_updated_fields(field_cache)
        return updated_fields, dependant_fields

    def delete_rows(
        self,
        user: AbstractUser,
        table: Table,
        row_ids: List[int],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        permanently_delete: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> TrashedRows:
        """
        Trashes existing rows of the given table based on row_ids.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row_ids: The ids of the rows that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the rows are deleted in the view.
            This can result in different permissions checks.
        :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param permanently_delete: If `true` the rows will be permanently deleted
            instead of trashed.
        :param signal_params: Additional parameters that are added to the signal.
        """

        self._check_permissions_with_view_fallback(
            DeleteDatabaseRowOperationType.type,
            DeleteViewRowOperationType.type,
            user,
            table,
            view,
            row_ids,
        )
        return self.force_delete_rows(
            user,
            table,
            row_ids,
            model=model,
            send_realtime_update=send_realtime_update,
            send_webhook_events=send_webhook_events,
            permanently_delete=permanently_delete,
            signal_params=signal_params,
        )

    def force_delete_rows(
        self,
        user: AbstractUser,
        table: Table,
        row_ids: List[int],
        model: Optional[Type[GeneratedTableModel]] = None,
        send_realtime_update: bool = True,
        send_webhook_events: bool = True,
        permanently_delete: bool = False,
        signal_params: Optional[Dict] = None,
    ) -> TrashedRows:
        """
        Trashes existing rows of the given table based on row_ids, without checking
        user permissions.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row_ids: The ids of the rows that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
         :param send_realtime_update: If set to false then it is up to the caller to
            send the rows_created or similar signal. Defaults to True.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :param permanently_delete: If `true` the rows will be permanently deleted
            instead of trashed.
        :param signal_params: Additional parameters that are added to the signal.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        """

        if signal_params is None:
            signal_params = {}

        workspace = table.database.workspace
        if model is None:
            model = table.get_model()

        non_unique_ids = get_non_unique_values(row_ids)
        if len(non_unique_ids) > 0:
            raise RowIdsNotUnique(non_unique_ids)

        rows = list(model.objects.filter(id__in=row_ids).enhance_by_fields())

        if len(row_ids) != len(rows):
            db_rows_ids = [db_row.id for db_row in rows]
            raise RowDoesNotExist(sorted(list(set(row_ids) - set(db_rows_ids))))

        before_return = before_rows_delete.send(
            self, rows=rows, user=user, table=table, model=model
        )

        if permanently_delete:
            trashed_rows = TrashedRows(row_ids=row_ids, table=table, table_id=table.id)
            # It's a bit of hack, but because the `trashed_rows` is never actually
            # created, it also doesn't have to be deleted in the
            # `permanently_delete_item` method.
            trashed_rows.delete = lambda *a, **k: None
            trash_item_type = trash_item_type_registry.get_by_model(trashed_rows)
            trash_item_type.permanently_delete_item(trashed_rows)
        else:
            trashed_rows = TrashedRows.objects.create(row_ids=row_ids, table=table)
            # It's a bit on a hack, but we're storing the fetched row objects on the
            # trashed_rows object, so that they can optionally be used later. This is
            # for example used when storing the names in the trash.
            trashed_rows.rows = rows

            TrashHandler.trash(user, workspace, table.database, trashed_rows)

        rows_deleted_counter.add(len(row_ids))

        updated_field_ids = []
        updated_fields = []
        for field_id, field_object in model._field_objects.items():
            updated_field_ids.append(field_id)
            field = field_object["field"]
            updated_fields.append(field)

        update_collector = FieldUpdateCollector(table, starting_row_ids=row_ids)
        field_cache = FieldCache()
        field_cache.cache_model(model)
        dependant_fields = []

        all_dependent_fields_grouped_by_level = (
            FieldDependencyHandler.group_all_dependent_fields_by_level_from_fields(
                updated_fields,
                field_cache,
                associated_relations_changed=True,
                database_id_prefilter=table.database_id,
            )
        )

        for depth, dependent_fields_level in enumerate(
            all_dependent_fields_grouped_by_level
        ):
            dependency_context = DependencyContext(depth=depth)
            for (
                table_id,
                dependant_field,
                path_to_starting_table,
            ) in dependent_fields_level:
                dependant_fields.append(dependant_field)
                dependant_field_type = field_type_registry.get_by_model(dependant_field)
                dependant_field_type.row_of_dependency_deleted(
                    dependant_field,
                    rows,
                    update_collector,
                    field_cache,
                    path_to_starting_table,
                    dependency_context,
                )
            update_collector.apply_updates_and_get_updated_fields(field_cache)

        from baserow.contrib.database.views.handler import ViewHandler

        ViewHandler().field_value_updated(updated_fields + dependant_fields)

        rows_deleted.send(
            self,
            rows=rows,
            user=user,
            table=table,
            model=model,
            before_return=before_return,
            send_realtime_update=send_realtime_update,
            send_webhook_events=send_webhook_events,
            fields=updated_fields,
            dependant_fields=dependant_fields,
            **signal_params,
        )

        return trashed_rows

    def recalculate_row_orders(self, table: Table, model: GeneratedTableModel = None):
        """
        Recalculates the order to whole numbers of all rows based on the existing
        position for the provided table.

        id     old_order    new_order
        1      1.5000       2.0000
        2      1.7500       3.0000
        3      0.7500       1.0000

        :param table: The table object for which the rows orders must be recalculated.
        :param model: The already generated model if any.
        """

        if model is None:
            model = table.get_model()

        recalculate_full_orders(model)

        row_orders_recalculated.send(
            self,
            table=table,
        )


def merge_values_expression(
    row: list[str | int | float | None],
    field_handlers: "list[UpsertFieldHandler]",
    query_params: list,
) -> sql.Composable:
    """
    Create a sql expression that will produce text value from a list of row values. Any
    value, that should be interpolated, will be added to provided `query_params` list.

    :param row: a list of values in a row
    :param field_handlers: a list of field types for a row. The number of handlers
            should equal the number of values in a row.
    :param query_params: param values container
    :return:
    """

    fields = []

    for val, field_handler in zip(row, field_handlers):
        fields.append(field_handler.get_field_concat_expression())
        query_params.append(field_handler.prepare_value(val))

    return UpsertRowsMappingHandler.SEPARATOR.join(fields)


class UpsertFieldHandler:
    """
    Helper class to handle field's upsert handling.
    """

    def __init__(self, table: Table, field_id: id):
        self.table = table
        # TODO: here we are using field id, but it may be so the field_id
        #  is `'id'` string.
        try:
            self._field_def = field_def = next(
                (
                    f
                    for f in table.get_model().get_field_objects()
                    if f["field"].id == field_id
                )
            )
        except StopIteration:
            raise FieldNotInTable(field_id)

        self.field: Field = field_def["field"]
        self.field_type: FieldType = field_def["type"]
        if not self.field_type.can_upsert:
            raise IncompatibleField(self.field.id)
        self.field_name = self.field.db_column

    def prepare_value(self, value: str) -> Any:
        return self.field_type.prepare_value_for_db(self.field, value)

    def get_field_concat_expression(self) -> sql.Composable:
        column_type = sql.SQL(self.get_column_type() or "text")
        return sql.SQL(" COALESCE(CAST({}::{} AS TEXT), '<NULL>')::TEXT ").format(
            sql.Placeholder(), column_type
        )

    def get_column_type(self) -> str | None:
        table_field: DjangoField = self.field_type.get_model_field(self.field)
        return table_field.db_type(db.connection)


class UpsertRowsMappingHandler:
    """
    Helper class for mapping new rows values to existing table rows during an upsert
    operation.

    This class processes upsert values from the provided data and matches them with
    existing row IDs in the database. The resulting mapping helps determine which
    imported rows should update existing ones.

    ### Usage:

    >>> importrows = ImportRowsMappingHandler(table, [1234], [['a'], ['b']])

    # Returns a dictionary where:
    # - Keys represent the index of the upsert values in the imported dataset.
    # - Values represent the corresponding row ID in the database.
    >>> importrows.process_map
    {0: 1, 1: 2}

    # In this example:
    # - The first imported value ['a'] (index 0) corresponds to the row with ID 1.
    # - The second imported value ['b'] (index 1) corresponds to the row with ID 2.
    """

    SEPARATOR = sql.SQL(" || '__-__' || ")
    PER_CHUNK = 100

    def __init__(
        self, table: Table, upsert_fields: list[int], upsert_values: list[list[Any]]
    ):
        self.table = table
        self.table_name = table.get_database_table_name()
        self.import_fields = [UpsertFieldHandler(table, fidx) for fidx in upsert_fields]
        self.upsert_values = upsert_values

    def validate(self):
        """
        Validates if upsert configuration conforms formal requirements
        :raises InvalidRowLength:
        """

        expected_length = len(self.import_fields)
        for ridx, uval in enumerate(self.upsert_values):
            if len(uval) != expected_length:
                raise InvalidRowLength(ridx)

    @cached_property
    def process_map(self) -> dict[int, int]:
        """
        Calculates a map between import row indexes and table row ids.
        """

        # no upsert value fields, no need for mapping
        if not self.import_fields:
            return {}

        script_template = sql.SQL(
            """
        CREATE TEMP TABLE table_upsert_indexes (id INT, upsert_value TEXT, group_index INT);

        CREATE TEMP TABLE table_import (id INT, upsert_value TEXT);

        CREATE TEMP VIEW table_import_indexes AS
                SELECT id, upsert_value, RANK()
                        OVER (PARTITION BY upsert_value ORDER BY id, upsert_value )
                        AS group_index
                FROM table_import ORDER BY id ;
        """
        )

        self.execute(script_template)
        self.insert_table_values()
        self.insert_imported_values()
        # this is just a list of pairs, not very usable.
        calculated = self.calculate_map()

        # map import row idx -> update row_id in table
        return {r[1]: r[0] for r in calculated}

    @cached_property
    def connection(self):
        return db.connection

    @cached_property
    def cursor(self):
        return self.connection.cursor()

    def execute(self, query, *args, **kwargs) -> "CursorWrapper":
        self.cursor.execute(query, *args, **kwargs)
        return self.cursor

    def insert_table_values(self):
        """
        Populates temp upsert comparison table with values from an exsisting table.
        Values from multiple source columns will be normalized to one text value.
        """

        columns = self.SEPARATOR.join(
            [
                sql.SQL("COALESCE(CAST({} AS TEXT), '<NULL>')::TEXT").format(
                    sql.Identifier(field.field_name)
                )
                for field in self.import_fields
            ]
        )

        query = sql.SQL(
            """WITH subq AS (SELECT r.id,  {} AS upsert_value FROM {} r WHERE NOT trashed)
                INSERT INTO table_upsert_indexes (id, upsert_value, group_index)
                SELECT id, upsert_value, RANK()
                        OVER (PARTITION BY upsert_value ORDER BY id, upsert_value )
                        AS group_index
                FROM subq ORDER BY id """
        ).format(
            columns, sql.Identifier(self.table_name)
        )  # nosec B608

        self.execute(query)

    def insert_imported_values(self):
        """
        Builds and executes bulk insert queries for upsert comparison values
        from import data.
        """

        for _chunk in chunks(enumerate(self.upsert_values), self.PER_CHUNK):
            # put all params (processed values) for the query into a container
            query_params = []
            rows_query = []
            for rowidx, row in _chunk:
                # per-row insert query
                query_params.append(rowidx)
                row_to_add = sql.SQL("({}, {})").format(
                    sql.Placeholder(),
                    merge_values_expression(row, self.import_fields, query_params),
                )
                rows_query.append(row_to_add)

            rows_placeholder = sql.SQL(",\n").join(rows_query)
            script_template = sql.SQL(
                "INSERT INTO table_import (id, upsert_value) VALUES {};"
            ).format(
                rows_placeholder
            )  # nosec B608
            self.execute(script_template, query_params)

    def calculate_map(self) -> list[tuple[int, int]]:
        """
        Calculates a map between imported row index -> table row id
        that can be used to detect if a row that is imported should be updated
        (mapping exists) or inserted as a new one.
        """

        q = sql.SQL(
            """
        SELECT t.id, i.id
            FROM table_upsert_indexes t
            JOIN table_import_indexes i
                ON (i.upsert_value = t.upsert_value
                    AND i.group_index = t.group_index);
        """
        )
        return self.execute(q).fetchall()
