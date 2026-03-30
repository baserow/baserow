import traceback
from typing import Any, Dict, List, NewType, Optional, Tuple, cast

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import DatabaseError, IntegrityError
from django.db.models import Q, QuerySet, Sum
from django.db.models.functions import Coalesce, Now
from django.utils import translation
from django.utils.translation import gettext as _

from opentelemetry import trace

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.constants import RESERVED_BASEROW_FIELD_NAMES
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.exceptions import (
    InvalidBaserowFieldName,
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    ReservedBaserowFieldNameException,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.operations import (
    CreateTableDatabaseTableOperationType,
    ListTablesDatabaseTableOperationType,
    OrderTablesDatabaseTableOperationType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.expressions import (
    BaserowTableFileUniques,
    BaserowTableRowCount,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.handler import TrashHandler
from baserow.core.usage.registries import USAGE_UNIT_MB
from baserow.core.user_files.models import UserFile
from baserow.core.utils import ChildProgressBuilder, Progress, find_unused_name, grouper

from .constants import (
    CREATED_BY_COLUMN_NAME,
    LAST_MODIFIED_BY_COLUMN_NAME,
    TABLE_CREATION,
)
from .exceptions import (
    FailedToLockTableDueToConflict,
    InitialTableDataDuplicateName,
    InitialTableDataLimitExceeded,
    InvalidInitialTableData,
    TableDoesNotExist,
    TableNotInDatabase,
)
from .models import Table, TableUsage, TableUsageUpdate
from .operations import (
    DeleteDatabaseTableOperationType,
    DuplicateDatabaseTableOperationType,
    UpdateDatabaseTableOperationType,
)
from .signals import table_created, table_deleted, table_updated, tables_reordered

BATCH_SIZE = 1024

TableForUpdate = NewType("TableForUpdate", Table)

tracer = trace.get_tracer(__name__)


class TableUsageHandler:
    @classmethod
    def calculate_table_storage_usage(cls, table_id):
        return UserFile.objects.filter(
            unique__in=BaserowTableFileUniques(table_id)
        ).aggregate(tot_MB=Coalesce(Sum("size"), 0) / USAGE_UNIT_MB)["tot_MB"]

    @classmethod
    def mark_table_for_usage_update(
        cls, table_id: int, row_count: int = 0
    ) -> Optional[TableUsageUpdate]:
        """
        Creates a new table usage log entry. This function can be called when an
        operation change the table row_count or the storage usage to create or update an
        entry so that the usage can be tracked and updated.

        :param table_id: The id of the table that needs to be updated.
        :param row_count: This represents the change in row count for the table
            identified by 'table_id'. `0` means that the row count has not changed but
            we still want to recalcuate the storage usage at the next update.
        :return: The created TableUsageUpdate object or None if the table_id is not
            valid.
        """

        try:
            return TableUsageUpdate.objects.create(
                table_id=table_id, row_count=row_count, timestamp=Now()
            )
        except IntegrityError as integrity_exc:
            if "violates foreign key constraint" in str(integrity_exc):
                # we can safely ignore the exception and don't try to
                # update usage for non existing tables
                return None

            raise integrity_exc

    @classmethod
    def create_tables_usage_for_new_database(cls, database_id: int):
        """
        Creates a TableUsageUpdate entry for each table in the database so that the
        usage can be tracked and updated.

        :param database_id: The id of the database that needs to be updated.
        """

        tables_in_database = TableHandler.get_tables().filter(database_id=database_id)

        entries = [
            TableUsageUpdate(
                table_id=table.id, row_count=BaserowTableRowCount(table.id)
            )
            for table in tables_in_database
        ]
        TableUsageUpdate.objects.bulk_create(entries, ignore_conflicts=True)

    @classmethod
    def update_tables_usage(cls) -> int:
        """
        Updates all the tables usage for the existing entries that have received updates
        since the last time, and creates the new ones for new tables if missing.

        NOTE: this function can be very expensive if there are a lot of tables or some
        very big table, so please make sure to call it in a background task.

        :return: The number of tables for which the usage has been updated or created.
        """

        # Since calculating the row count and storage usage can be expensive, we
        # use a small chunk size to process the updates in smaller batches.
        table_usage_updates_qs = TableUsageUpdate.objects.all()
        updated = cls._update_existing_tables_usage(
            table_usage_updates_qs, chunk_size=1
        )

        tables_without_usage_qs = TableHandler.get_tables().filter(
            Q(usage=None), database__workspace__template__isnull=True
        )
        created = cls._create_missing_tables_usage(
            tables_without_usage_qs, chunk_size=1
        )

        return updated + created

    @classmethod
    def _bulk_create_or_update(cls, table_ids: List[int]) -> List[TableUsage]:
        """
        Creates or updates the table usage for the provided table ids. It uses
        `bulk_create` to do this in a single query.

        :param table_ids: The ids of the tables that need to be updated.
        :return: The list of created or updated TableUsage objects.
        """

        entries = []
        for table_id in table_ids:
            table_usage = TableUsage(
                table_id=table_id,
                row_count=BaserowTableRowCount(table_id),
                row_count_updated_at=Now(),
                storage_usage=cls.calculate_table_storage_usage(table_id),
                storage_usage_updated_at=Now(),
            )
            entries.append(table_usage)

        return TableUsage.objects.bulk_create(
            entries,
            update_conflicts=True,
            update_fields=[
                "row_count",
                "row_count_updated_at",
                "storage_usage",
                "storage_usage_updated_at",
            ],
            unique_fields=["table_id"],
        )

    @classmethod
    def _create_missing_tables_usage(
        cls, table_qs: QuerySet[Table], chunk_size=10
    ) -> int:
        """
        Counts how many rows each user table has and stores the count
        for later reference.

        :param table_qs: The queryset containing the tables that need to be
            updated.
        :param chunk_size: The number of tables to process at once.
        :returns: The number of tables counted.
        """

        total_tables_counted = 0

        for table_group in grouper(chunk_size, table_qs.only("id").iterator(1000)):
            created_table_usages = cls._bulk_create_or_update(
                [table.id for table in table_group]
            )

            total_tables_counted += len(created_table_usages)

        return total_tables_counted

    @classmethod
    def _update_existing_tables_usage(
        cls, usage_update_qs: QuerySet[TableUsageUpdate], chunk_size=10
    ) -> int:
        """
        Recalculates the row count and storage usage for the tables that have changed
        and have a TableUsageUpdate entry, and then delete them.

        :param usage_update_qs: The queryset containing the table usage updates that
            need to be processed.
        :param chunk_size: The number of tables to process at once.
        :returns: The number of tables counted.
        """

        total_tables_counted = 0

        for chunk in grouper(
            chunk_size, usage_update_qs.values("table_id").distinct().iterator(1000)
        ):
            table_ids = [u["table_id"] for u in chunk]

            cls._bulk_create_or_update(table_ids)
            TableUsageUpdate.objects.filter(table_id__in=table_ids).delete()

            total_tables_counted += len(table_ids)

        return total_tables_counted


class TableHandler(metaclass=baserow_trace_methods(tracer)):
    @classmethod
    def get_tables(
        cls, base_queryset: Optional[QuerySet[Table]] = None
    ) -> QuerySet[Table]:
        """
        Returns a queryset containing all the tables that are not trashed.

        :param base_queryset: specify a base queryset to use. If not provided, the
            default Table queryset will be used.
        :return: The queryset containing all the tables that are not trashed.
        """

        if base_queryset is None:
            base_queryset = Table.objects.all()

        return base_queryset.filter(
            trashed=False,
            database__trashed=False,
            database__workspace__trashed=False,
        )

    def list_workspace_tables(
        self, user: AbstractUser, workspace, include_trashed=False, base_queryset=None
    ) -> QuerySet[Table]:
        """
        Lists available tables for a user/workspace combination.

        :user: The user on whose behalf we want to return tables.
        :workspace: The workspace for which the tables should be returned.
        :base_queryset: specify a base queryset to use.
        :return: Iterator over returned tables.
        """

        table_qs = base_queryset if base_queryset else Table.objects.all()

        table_qs = (
            table_qs.filter(database__workspace=workspace)
            .select_related("database__workspace", "data_sync")
            .order_by("database_id", "order", "id")
        )

        if not include_trashed:
            table_qs = self.get_tables(table_qs)

        return CoreHandler().filter_queryset(
            user,
            ListTablesDatabaseTableOperationType.type,
            table_qs,
            workspace=workspace,
        )

    def get_table(
        self, table_id: int, base_queryset: Optional[QuerySet] = None
    ) -> Table:
        """
        Selects a table with a given id from the database.

        :param table_id: The identifier of the table that must be returned.
        :param base_queryset: The base queryset from where to select the table
            object from. This can for example be used to do a `select_related`.
        :raises TableDoesNotExist: When the table with the provided id does not exist.
        :return: The requested table of the provided id.
        """

        if base_queryset is None:
            base_queryset = Table.objects

        try:
            table = base_queryset.select_related(
                "database__workspace", "data_sync"
            ).get(id=table_id)
        except Table.DoesNotExist:
            raise TableDoesNotExist(f"The table with id {table_id} does not exist.")

        if TrashHandler.item_has_a_trashed_parent(table):
            raise TableDoesNotExist(f"The table with id {table_id} does not exist.")

        return table

    def get_table_for_update(
        self, table_id: int, nowait: bool = False
    ) -> TableForUpdate:
        """
        Provide a type hint for tables that need to be updated.
        :param table_id: The id of the table that needs to be updated.
        :param nowait: Whether to wait to get the lock on the table or raise a
            DatabaseError not able to do so immediately.
        :return: The table that needs to be updated.
        :raises: FailedToLockTableDueToConflict if nowait is True and the table was not
            able to be locked for update immediately.
        """

        try:
            return cast(
                TableForUpdate,
                self.get_table(
                    table_id,
                    base_queryset=Table.objects.select_for_update(
                        of=("self",), nowait=nowait
                    ),
                ),
            )
        except DatabaseError as e:
            if "could not obtain lock on row" in traceback.format_exc():
                raise FailedToLockTableDueToConflict() from e
            else:
                raise e

    def get_tables_order(self, database: Database) -> List[int]:
        """
        Returns the tables in the database ordered by the order field.

        :param database: The database that the tables belong to.
        :return: A list containing the order of the tables in the database.
        """

        return [table.id for table in database.table_set.order_by("order")]

    def create_table(
        self,
        user: AbstractUser,
        database: Database,
        name: str,
        data: Optional[List[List[Any]]] = None,
        first_row_header: bool = True,
        fill_example: bool = False,
        progress: Optional[Progress] = None,
    ):
        """
        Creates a new table from optionally provided data. If no data is specified,
        and fill_example is True, the new table will contain demo data. If fill_example
        is `False` the table will be empty.
        Send a `table_created` signal at the end of the process.

        :param user: The user on whose behalf the table is created.
        :param database: The database that the table instance belongs to.
        :param name: The name of the table is created.
        :param data: A list containing all the rows that need to be inserted is
            expected. All the values will be inserted in the database.
        :param first_row_header: Indicates if the first row are the fields. The names
            of these rows are going to be used as fields. If `fields` is provided,
            this options is ignored.
        :param fill_example: Fill the table with example field and data.
        :param progress: An optional progress instance if you want to track the progress
            of the task.
        :return: The created table and the error report.
        """

        CoreHandler().check_permissions(
            user,
            CreateTableDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        if progress:
            progress.increment(0, state=TABLE_CREATION)

        if data is not None:
            (
                fields,
                data,
            ) = self.normalize_initial_table_data(
                data, first_row_header=first_row_header
            )
        else:
            with translation.override(user.profile.language):
                if fill_example:
                    fields, data = self.get_example_table_field_and_data()
                else:
                    fields, data = self.get_minimal_table_field_and_data()

        table = self.create_table_and_fields(user, database, name, fields)

        _, error_report = RowHandler().import_rows(
            user,
            table,
            data=data,
            progress=progress,
            send_realtime_update=False,
        )

        table_created.send(self, table=table, user=user)

        return table, error_report

    def create_table_and_fields(
        self,
        user: AbstractUser,
        database: Database,
        name: str,
        fields: List[Tuple[str, str, Dict[str, Any]]],
        **table_kwargs,
    ) -> Table:
        """
        Creates a new table with the specified fields. Also creates a default grid view
        for this table.

        :param user: The user on whose behalf the table is created.
        :param database: The database that the table instance belongs to.
        :param name: The name of the table is created.
        :param fields: You specify the field configuration with this parameter. The
            tuples content is the field name, then the field type and the field
            configuration. You can add an optional `field_options` dict for the
            field_options of the created view.
        """

        last_order = Table.get_last_order(database)
        table = Table.objects.create(
            database=database, order=last_order, name=name, **table_kwargs
        )

        # Let's create the fields before creating the model so that the whole
        # table schema is created right away.
        field_options_dict = {}
        for index, (name, field_type_name, field_config) in enumerate(fields):
            field_options = field_config.pop("field_options", None)
            field_type = field_type_registry.get(field_type_name)
            FieldModel = field_type.model_class

            fields[index] = FieldModel.objects.create(
                table=table, order=index, primary=index == 0, name=name, **field_config
            )
            if field_options:
                field_options_dict[fields[index].id] = field_options

        # Creates a default view
        view_handler = ViewHandler()

        with translation.override(user.profile.language):
            view = view_handler.create_view(
                user, table, GridViewType.type, name=_("Grid")
            )

        # Fix field_options if any
        if field_options_dict:
            view_handler.update_field_options(
                user=user,
                view=view,
                field_options=field_options_dict,
                fields=fields,
            )

        # Create the table schema in the database.
        with safe_django_schema_editor() as schema_editor:
            # Django only creates indexes when the model is managed.
            model = table.get_model(managed=True)
            schema_editor.create_model(model)

        return table

    def normalize_initial_table_data(
        self, data: List[List[Any]], first_row_header: bool
    ) -> Tuple[List, List]:
        """
        Normalizes the provided initial table data. The amount of columns will be made
        equal for each row. The header and the rows will also be separated.

        :param data: A list containing all the provided rows.
        :param first_row_header: Indicates if the first row is the header. For each
            of these header columns a field is going to be created.
        :raises InvalidInitialTableData: When the data doesn't contain a column or row.
        :raises MaxFieldNameLengthExceeded: When the provided name is too long.
        :raises InitialTableDataDuplicateName: When duplicates exit in field names.
        :raises ReservedBaserowFieldNameException: When the field name is reserved by
            Baserow.
        :raises InvalidBaserowFieldName: When the field name is invalid (empty).
        :return: A list containing the field names with a type and a list containing all
            the rows.
        """

        if len(data) == 0:
            raise InvalidInitialTableData("At least one row should be provided.")

        limit = settings.INITIAL_TABLE_DATA_LIMIT
        if limit and len(data) > limit:
            raise InitialTableDataLimitExceeded(
                f"It is not possible to import more than "
                f"{settings.INITIAL_TABLE_DATA_LIMIT} rows when creating a table."
            )

        largest_column_count = len(max(data, key=len))

        if largest_column_count == 0:
            raise InvalidInitialTableData("At least one column should be provided.")

        fields = data.pop(0) if first_row_header else []

        for i in range(len(fields), largest_column_count):
            fields.append(_("Field %d") % (i + 1,))

        if len(fields) > settings.MAX_FIELD_LIMIT:
            raise MaxFieldLimitExceeded(
                f"Fields count exceeds the limit of {settings.MAX_FIELD_LIMIT}"
            )

        # Stripping whitespace from field names is already done by
        # TableCreateSerializer however we repeat to ensure that non API usages of
        # this method is consistent with api usage.
        field_name_set = {str(name).strip() for name in fields}

        if len(field_name_set) != len(fields):
            raise InitialTableDataDuplicateName()

        max_field_name_length = Field.get_max_name_length()
        long_field_names = [x for x in field_name_set if len(x) > max_field_name_length]

        if len(long_field_names) > 0:
            raise MaxFieldNameLengthExceeded(max_field_name_length)

        if len(field_name_set.intersection(RESERVED_BASEROW_FIELD_NAMES)) > 0:
            raise ReservedBaserowFieldNameException()

        if "" in field_name_set:
            raise InvalidBaserowFieldName()

        fields_with_type = [(field_name, "text", {}) for field_name in fields]
        result = [[str(value) for value in row] for row in data]

        return fields_with_type, result

    def get_example_table_field_and_data(self):
        """
        Generates fields and data with some initial example data.
        """

        fields = [
            (_("Name"), "text", {}),
            (_("Notes"), "long_text", {"field_options": {"width": 400}}),
            (_("Active"), "boolean", {"field_options": {"width": 100}}),
        ]
        data = [["", "", False], ["", "", False]]
        return fields, data

    def get_minimal_table_field_and_data(self):
        """
        Generates fields and data for an empty table.
        """

        fields = [
            (_("Name"), "text", {}),
        ]
        data = []
        return fields, data

    def update_table_by_id(self, user: AbstractUser, table_id: int, name: str) -> Table:
        """
        Updates an existing table instance.

        :param user: The user on whose behalf the table is updated.
        :param table_id: The id of the table that needs to be updated.
        :param name: The name to be updated.
        :raises ValueError: When the provided table is not an instance of Table.
        :return: The updated table instance.
        """

        table = self.get_table_for_update(table_id)
        return self.update_table(user, table, name)

    def update_table(self, user: AbstractUser, table: Table, name: str) -> Table:
        """
        Updates an existing table instance.

        :param user: The user on whose behalf the table is updated.
        :param table: The table instance that needs to be updated.
        :param name: The name to be updated.
        :raises ValueError: When the provided table is not an instance of Table.
        :return: The updated table instance.
        """

        if not isinstance(table, Table):
            raise ValueError("The table is not an instance of Table")

        CoreHandler().check_permissions(
            user,
            UpdateDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        table.name = name
        table.save()

        table_updated.send(self, table=table, user=user)

        return table

    def order_tables(self, user: AbstractUser, database: Database, order: List[int]):
        """
        Updates the order of the tables in the given database. The order of the views
        that are not in the `order` parameter set to `0`.

        :param user: The user on whose behalf the tables are ordered.
        :param database: The database of which the views must be updated.
        :param order: A list containing the table ids in the desired order.
        :raises TableNotInDatabase: If one of the table ids in the order does not belong
            to the database.
        """

        CoreHandler().check_permissions(
            user,
            OrderTablesDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        all_tables = Table.objects.filter(database_id=database.id)

        user_tables = CoreHandler().filter_queryset(
            user,
            OrderTablesDatabaseTableOperationType.type,
            all_tables,
            workspace=database.workspace,
        )

        table_ids = user_tables.values_list("id", flat=True)

        for table_id in order:
            if table_id not in table_ids:
                raise TableNotInDatabase(table_id)

        full_order = Table.order_objects(all_tables, order)
        tables_reordered.send(self, database=database, order=full_order, user=user)

    def find_unused_table_name(self, database: Database, proposed_name: str) -> str:
        """
        Finds an unused name for a table in a database.

        :param database: The database that the table belongs to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        existing_tables_names = list(database.table_set.values_list("name", flat=True))
        return find_unused_name([proposed_name], existing_tables_names, max_length=255)

    def _create_related_link_fields_in_existing_tables_to_import(
        self, serialized_table: Dict[str, Any], id_mapping: Dict[str, Any]
    ) -> List[Tuple[Table, Dict[str, Any]]]:
        """
        Creates extra serialized field dicts to pass to the table importer so it will
        create the reverse link row fields in any existing tables.

        :param serialized_table: The serialized table.
        :param id_mapping: The id mapping.
        :return : A list of external tables with the link row fields to import into
            them.
        """

        from baserow.contrib.database.fields.field_types import LinkRowFieldType

        external_fields = []
        for serialized_field in serialized_table["fields"]:
            if serialized_field["type"] != LinkRowFieldType.type:
                continue

            link_row_table_id = serialized_field.get("link_row_table_id", None)
            self_referencing_field = link_row_table_id == serialized_table["id"]
            link_row_table = self.get_table(link_row_table_id)
            has_related_field = serialized_field.get("link_row_related_field_id")
            id_mapping["database_tables"][link_row_table_id] = link_row_table_id

            if self_referencing_field or not has_related_field:
                continue

            related_field_name = FieldHandler().find_next_unused_field_name(
                link_row_table, [serialized_table["name"]]
            )
            # We deliberately want to use a negative ID for the newly created related
            # field because it can't clash with another existing field ID. It doesn't
            # matter that it's negative because it get a new unique when it's
            # imported later on.
            related_field_id = -len(external_fields)
            serialized_field["link_row_related_field_id"] = related_field_id
            serialized_related_link_row_field = {
                "id": related_field_id,
                "name": related_field_name,
                "type": LinkRowFieldType.type,
                "link_row_table_id": serialized_table["id"],
                "link_row_related_field_id": serialized_field["id"],
                "order": Field.get_last_order(link_row_table),
            }
            external_fields.append((link_row_table, serialized_related_link_row_field))

        return external_fields

    def duplicate_table(
        self,
        user: AbstractUser,
        table: Table,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Table:
        """
        Duplicates an existing table instance.

        :param user: The user on whose behalf the table is duplicated.
        :param table: The table instance that needs to be duplicated.
        :param progress: A progress object that can be used to report progress.
        :raises ValueError: When the provided table is not an instance of Table.
        :return: The duplicated table instance.
        """

        if not isinstance(table, Table):
            raise ValueError("The table is not an instance of Table")

        start_progress, export_progress, import_progress = 10, 30, 60
        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        progress.increment(by=start_progress)

        database = table.database

        CoreHandler().check_permissions(
            user,
            DuplicateDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=table,
        )

        database_type = application_type_registry.get_by_model(database)

        config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
        )

        serialized_tables = database_type.export_tables_serialized([table], config)

        # Set a unique name for the table to import back as a new one.
        exported_table = serialized_tables[0]
        exported_table["name"] = self.find_unused_table_name(database, table.name)
        exported_table["order"] = Table.get_last_order(database)

        # It can happen that a field, filter, etc has a reference to a field in
        # another table. This can result in an error because that field id is not in
        # the field mapping. Therefore, we're fetching all the related field ids in
        # the table and add those to the mapping. The key and value is the same
        # because those field ids haven't changed.
        all_table_dependency_field_ids = FieldDependency.objects.filter(
            Q(dependant__table_id=table.id) & ~Q(dependency__table_id=table.id)
        ).values_list("dependency_id", flat=True)
        all_table_dependency_field_ids = {
            field_id: field_id for field_id in all_table_dependency_field_ids
        }

        # It can happen that a field has a reference to another view. We would
        # therefore need to construct a mapping that contains all the existing views,
        # and they will remain the same
        all_database_views_ids = View.objects.filter(
            table__database_id=table.database_id
        ).values_list("id")
        all_database_view_ids = {
            view_id[0]: view_id[0] for view_id in all_database_views_ids
        }

        id_mapping: Dict[str, Any] = {
            "database_tables": {},
            "database_fields": all_table_dependency_field_ids,
            "database_views": all_database_view_ids,
            # The properties below must be kept in sync with
            # `src/baserow/contrib/database/views/registries.py::import_serialized`
            "database_view_filters": {},
            "database_view_filter_groups": {},
            "database_view_sortings": {},
            "database_view_group_bys": {},
            "database_view_decorations": {},
            # We have to create the `database_field_select_options` because that's
            # otherwise not created later on.
            "database_field_select_options": {},
        }

        link_fields_to_import_to_existing_tables = (
            self._create_related_link_fields_in_existing_tables_to_import(
                exported_table, id_mapping
            )
        )
        progress.increment(by=export_progress)

        imported_tables = database_type.import_tables_serialized(
            database,
            [exported_table],
            id_mapping,
            config,
            external_table_fields_to_import=link_fields_to_import_to_existing_tables,
            progress_builder=progress.create_child_builder(
                represents_progress=import_progress
            ),
        )

        new_table_clone = imported_tables[0]

        table_created.send(self, table=new_table_clone, user=user)

        return new_table_clone

    def delete_table_by_id(self, user: AbstractUser, table_id: int):
        """
        Moves to the trash an existing an existing table instance if the user
        has access to the related workspace.
        The table deleted signals are also fired.

        :param user: The user on whose behalf the table is deleted.
        :param table_id: The table id of the table that needs to be deleted.
        :raises ValueError: When the provided table is not an instance of Table.
        """

        table = self.get_table_for_update(table_id)
        self.delete_table(user, table)

    def delete_table(self, user: AbstractUser, table: Table):
        """
        Moves to the trash an existing table instance if the user has access
        to the related workspace.
        The table deleted signals are also fired.

        :param user: The user on whose behalf the table is deleted.
        :param table: The table instance that needs to be deleted.
        :raises ValueError: When the provided table is not an instance of Table.
        """

        if not isinstance(table, Table):
            raise ValueError("The table is not an instance of Table")

        CoreHandler().check_permissions(
            user,
            DeleteDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        TrashHandler.trash(user, table.database.workspace, table.database, table)

        table_deleted.send(self, table_id=table.id, table=table, user=user)

    def create_created_by_and_last_modified_by_fields(self, table: "Table") -> None:
        """
        Creates the created_by and last_modified_by fields for the provided
        table if they have not yet been created.

        :param table: Table that should have created_by and last_modified_by
            fields.
        """

        last_modified_by_column_added = table.last_modified_by_column_added
        created_by_column_added = table.created_by_column_added
        if last_modified_by_column_added and created_by_column_added:
            return

        table.last_modified_by_column_added = True
        table.created_by_column_added = True
        model = table.get_model(use_cache=False, field_ids=[])

        with safe_django_schema_editor(atomic=False) as schema_editor:
            if not last_modified_by_column_added:
                last_modified_by_field = model._meta.get_field(
                    LAST_MODIFIED_BY_COLUMN_NAME
                )
                schema_editor.add_field(model, last_modified_by_field)

            if not created_by_column_added:
                created_by_field = model._meta.get_field(CREATED_BY_COLUMN_NAME)
                schema_editor.add_field(model, created_by_field)

        table.save(
            update_fields=["created_by_column_added", "last_modified_by_column_added"]
        )
