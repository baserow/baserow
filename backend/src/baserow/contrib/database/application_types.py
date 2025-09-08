from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional, Set, Tuple
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.core.management.color import no_style
from django.db import connection, models
from django.db.models import Prefetch, QuerySet
from django.db.transaction import Atomic
from django.urls import include, path
from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.database.api.serializers import DatabaseSerializer
from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils.field_constraint import (
    build_django_field_constraints,
)
from baserow.contrib.database.models import Database, Field, View
from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.db import specific_queryset
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Workspace
from baserow.core.registries import (
    ApplicationType,
    ImportExportConfig,
    serialization_processor_registry,
)
from baserow.core.storage import ExportZipFile
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder, Progress, grouper

from .constants import (
    EXPORT_SERIALIZED_EXPORTING_TABLE,
    IMPORT_SERIALIZED_IMPORTING_TABLE_DATA,
    IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE,
)
from .data_sync.registries import data_sync_type_registry
from .db.atomic import read_repeatable_single_database_atomic_transaction
from .export_serialized import DatabaseExportSerializedStructure
from .field_rules.handlers import FieldRuleHandler
from .field_rules.models import FieldRule
from .fields.utils import DeferredFieldImporter, DeferredForeignKeyUpdater
from .search.handler import SearchHandler
from .table.models import GeneratedTableModel, Table


@dataclass
class ImportedFields:
    table_fields_by_name: Dict[Table, Dict[str, Field]]
    fields_without_dependencies: List[Field]
    fields_with_dependencies: List[Field]
    field_cache: FieldCache


class DatabaseApplicationType(ApplicationType):
    type = "database"
    model_class = Database
    serializer_mixins = [DatabaseSerializer]
    instance_serializer_class = DatabaseSerializer
    serializer_field_names = ["tables"]
    # Mark the request serializer field names as empty, otherwise
    # the polymorphic request serializer will try and serialize tables.
    request_serializer_field_names = []

    # Database applications are imported first.
    import_application_priority = 2

    def pre_delete(self, database):
        """
        When a database is deleted we must also delete the related tables via the table
        handler.
        """

        database_tables = (
            database.table_set(manager="objects_and_trash")
            .all()
            .select_related("database__workspace")
            .prefetch_related("field_set")
        )

        for table in database_tables:
            TrashHandler.permanently_delete(table)

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("database/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application) -> Atomic:
        return read_repeatable_single_database_atomic_transaction(application.id)

    def export_tables_serialized(
        self,
        tables: List[Table],
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict[str, Any]]:
        """
        Exports the tables provided  to a serialized format that can later
        be imported via the `import_tables_serialized`.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=len(tables))

        serialized_tables: List[Dict[str, Any]] = []

        for table in tables:
            fields = table.field_set.all()
            serialized_fields = []
            for f in fields:
                field = f.specific
                field_type = field_type_registry.get_by_model(field)
                serialized_fields.append(field_type.export_serialized(field))

            table_cache: Dict[str, Any] = {}
            workspace = table.get_root()
            if workspace is not None:
                table_cache["workspace_id"] = workspace.id
            serialized_views = []
            for v in table.view_set.all():
                view = v.specific
                view_type = view_type_registry.get_by_model(view)
                serialized_views.append(
                    view_type.export_serialized(
                        view, import_export_config, table_cache, files_zip, storage
                    )
                )

            serialized_rows = []
            row_count_limit = settings.BASEROW_IMPORT_EXPORT_TABLE_ROWS_COUNT_LIMIT
            export_all_table_rows = not import_export_config.only_structure
            if export_all_table_rows:
                model = table.get_model(fields=fields, add_dependencies=False)
                row_queryset = model.objects.all()[: row_count_limit or None]

                row_progress = progress.create_child(1, row_queryset.count())
                if table.created_by_column_added:
                    row_queryset = row_queryset.select_related("created_by")
                if table.last_modified_by_column_added:
                    row_queryset = row_queryset.select_related("last_modified_by")
                for row in row_queryset:
                    serialized_row = DatabaseExportSerializedStructure.row(
                        id=row.id,
                        order=str(row.order),
                        created_on=row.created_on.isoformat(),
                        updated_on=row.updated_on.isoformat(),
                        created_by=getattr(row, "created_by", None),
                        last_modified_by=getattr(row, "last_modified_by", None),
                    )
                    for field_object in model._field_objects.values():
                        field_name = field_object["name"]
                        field_type = field_object["type"]
                        serialized_row[
                            field_name
                        ] = field_type.get_export_serialized_value(
                            row, field_name, table_cache, files_zip, storage
                        )
                    serialized_rows.append(serialized_row)
                    row_progress.increment(
                        state=EXPORT_SERIALIZED_EXPORTING_TABLE + str(table.name)
                    )
            else:
                progress.increment()

            serialized_data_sync = None
            serialized_field_rules = []
            if hasattr(table, "data_sync"):
                data_sync = table.data_sync.specific
                data_sync_type = data_sync_type_registry.get_by_model(data_sync)
                serialized_data_sync = data_sync_type.export_serialized(data_sync)

            if hasattr(table, "field_rules"):
                field_rules_handler = FieldRuleHandler(table)

                for (
                    rule,
                    rule_type,
                ) in field_rules_handler.applicable_rules_with_types:
                    exported_field_rule = field_rules_handler.export_rule(rule)
                    serialized_field_rules.append(exported_field_rule)

            structure = DatabaseExportSerializedStructure.table(
                id=table.id,
                name=table.name,
                order=table.order,
                fields=serialized_fields,
                views=serialized_views,
                rows=serialized_rows,
                data_sync=serialized_data_sync,
                field_rules=serialized_field_rules,
            )

            for serialized_structure in serialization_processor_registry.get_all():
                extra_data = serialized_structure.export_serialized(
                    workspace, table, import_export_config
                )
                if extra_data is not None:
                    structure.update(**extra_data)
            serialized_tables.append(structure)

        return serialized_tables

    def export_serialized(
        self,
        database: Database,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Dict[str, Any]:
        """
        Exports the database application type to a serialized format that can later
        be imported via the `import_serialized`.
        """

        tables = (
            database.table_set.all()
            .select_related("data_sync")
            .prefetch_related(
                Prefetch("field_set", queryset=specific_queryset(Field.objects.all())),
                "field_set__select_options",
                Prefetch(
                    "view_set",
                    queryset=specific_queryset(
                        View.objects.all().select_related("owned_by")
                    ),
                ),
                "view_set__viewfilter_set",
                "view_set__filter_groups",
                "view_set__viewsort_set",
                "view_set__viewgroupby_set",
                "view_set__viewdecoration_set",
                "data_sync__synced_properties",
                Prefetch(
                    "field_rules", queryset=specific_queryset(FieldRule.objects.all())
                ),
            )
        )

        serialized_tables = self.export_tables_serialized(
            tables, import_export_config, files_zip, storage, progress_builder
        )

        serialized = super().export_serialized(
            database, import_export_config, files_zip, storage
        )
        serialized.update(
            **DatabaseExportSerializedStructure.database(tables=serialized_tables)
        )

        return serialized

    def _ops_count_for_import_tables_serialized(
        self,
        serialized_tables: List[Dict[str, Any]],
        external_table_fields_to_import: List[Tuple[Table, Dict[str, Any]]] = None,
    ) -> int:
        return (
            +
            # Creating each table
            len(serialized_tables)
            +
            # Creating each model table
            len(serialized_tables)
            + sum(
                [
                    # Inserting every field
                    len(table["fields"]) +
                    # Inserting every field
                    len(table["views"]) +
                    # Converting every row
                    len(table["rows"]) +
                    # Inserting every row
                    len(table["rows"]) +
                    # After each field
                    len(table["fields"])
                    for table in serialized_tables
                ]
            )
            + len(external_table_fields_to_import or [])
        )

    def init_application(self, user, application: Database) -> None:
        """
        Creates a new minimal table instance and a grid view for the newly
        created application.

        :param user: The user that creates the application.
        :param application: The application to initialize with data.
        """

        with translation.override(user.profile.language):
            first_table_name = _("Table")

        return TableHandler().create_table(
            user, application, first_table_name, fill_example=True
        )

    def _import_table_fields(
        self,
        serialized_tables: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        import_export_config: ImportExportConfig,
        external_table_fields_to_import: List[Tuple[Table, Dict[str, Any]]],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
        progress: Progress,
    ) -> ImportedFields:
        """
        Import the fields from the serialized data in the correct order based on their
        dependencies.

        :param serialized_tables: The serialized tables to import the fields from.
        :param id_mapping: A mapping of any table ids that might be referenced in
            serialized_tables to their new/existing ids to use in this import.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param external_table_fields_to_import: An optional list of fields which should
            also be imported. These fields will be imported into the existing table
            provided in the first item in the tuple, the second being the serialized
            field to import.
        :param deferred_fk_update_collector: A collector that collects all the foreign
            keys to update them later when the model with all the fields is created.
        :param progress: A progress used to report progress of the import.
        :return: The imported fields.
        """

        field_cache = FieldCache()
        table_fields_by_name = {}
        deferred_field_importer = DeferredFieldImporter()

        # Create a mapping between the old field id and the field name. This is used
        # to resolve dependencies between fields.
        database_fields_map: Dict[int, str] = {}
        primary_table_fields_map: Dict[int, int] = {}
        for serialized_table in serialized_tables:
            for serialized_field in serialized_table["fields"]:
                database_fields_map[serialized_field["id"]] = serialized_field
                if serialized_field["primary"]:
                    primary_table_fields_map[serialized_table["id"]] = serialized_field[
                        "id"
                    ]

        id_mapping["database_fields_map"] = database_fields_map
        id_mapping["primary_table_fields_map"] = primary_table_fields_map

        def _import_field_serialized(serialized_table, serialized_field):
            """
            Create the field instance and add it to the table_fields_by_name mapping.
            The logic is wrapped in a function to allow using it for deferred imports.
            """

            table_instance = serialized_table["_object"]
            field_type = field_type_registry.get(serialized_field["type"])
            field_instance = field_type.import_serialized(
                table_instance,
                serialized_field,
                import_export_config,
                id_mapping,
                deferred_fk_update_collector,
            )
            serialized_table["field_instances"].append(field_instance)
            if table_instance not in table_fields_by_name:
                table_fields_by_name[table_instance] = {}
            table_fields_by_name[table_instance][field_instance.name] = field_instance
            table_name = serialized_table["name"]
            progress.increment(
                state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE}{table_name}"
            )
            return field_instance

        fields_without_dependencies: List[Field] = []
        for serialized_table in serialized_tables:
            table_instance = serialized_table["_object"]
            for serialized_field in serialized_table["fields"]:
                field_type = field_type_registry.get(serialized_field["type"])
                field_deps = (
                    field_type.get_field_depdendencies_before_import_serialized(
                        serialized_field,
                        id_mapping["database_fields_map"],
                        id_mapping["primary_table_fields_map"],
                    )
                )

                # If the field has dependencies, we want to defer the import of the
                # field until all the dependencies have been imported.
                if field_deps:
                    import_field_callback = partial(
                        _import_field_serialized, serialized_table, serialized_field
                    )

                    deferred_field_importer.add_deferred_field_import(
                        table_instance,
                        serialized_field["name"],
                        field_deps,
                        import_field_callback,
                    )
                else:
                    # If the field has no dependencies, we can import it right away.
                    field_instance = _import_field_serialized(
                        serialized_table, serialized_field
                    )
                    fields_without_dependencies.append(field_instance)

        # Now that we have all the fields and their dependencies we can import all the
        # remaining fields in the correct order.
        fields_with_dependencies = deferred_field_importer.run_deferred_field_imports(
            id_mapping["database_field_names"]
        )

        deferred_fk_update_collector.run_deferred_fk_updates(
            id_mapping, "database_fields"
        )

        for external_table, serialized_field in external_table_fields_to_import or []:
            field_type = field_type_registry.get(serialized_field["type"])
            external_field = field_type.import_serialized(
                external_table,
                serialized_field,
                import_export_config,
                id_mapping,
                deferred_fk_update_collector,
            )
            SearchHandler.schedule_update_search_data(
                external_table, fields=[external_field]
            )
            progress.increment()

        deferred_fk_update_collector.run_deferred_fk_updates(
            id_mapping, "database_fields"
        )

        # For each field we call `after_import_serialized` which ensures that
        # formulas recalculate themselves now that all fields exist.
        for field_instance in fields_without_dependencies + fields_with_dependencies:
            field_type = field_type_registry.get_by_model(field_instance)
            field_type.after_import_serialized(field_instance, field_cache, id_mapping)

        # The loop above might have recalculated the formula fields in the list,
        # we need to refresh the instances we have as a result as they might be stale.
        for table_fields in table_fields_by_name.values():
            for field_instance in table_fields.values():
                field_type = field_type_registry.get_by_model(field_instance)
                if field_type.needs_refresh_after_import_serialized:
                    field_instance.refresh_from_db()

        return ImportedFields(
            table_fields_by_name=table_fields_by_name,
            fields_without_dependencies=fields_without_dependencies,
            fields_with_dependencies=fields_with_dependencies,
            field_cache=field_cache,
        )

    def import_tables_serialized(
        self,
        database: Database,
        serialized_tables: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        import_export_config: ImportExportConfig,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
        external_table_fields_to_import: List[Tuple[Table, Dict[str, Any]]] = None,
    ) -> List[Table]:
        """
        Imports tables exported by the `export_tables_serialized` method. Look at
        `import_serialized` to know how to call this function.

        :param database: The database to import the serialized tables into.
        :param serialized_tables: The serialized tables to import.
        :param id_mapping: A mapping of any table ids that might be referenced in
            serialized_tables to their new/existing ids to use in this import.
        :param files_zip: An optional zip of files which can be used to retrieve
            imported files from
        :param storage: An optional place to persist any user files if importing files
            from a the above file_zip.
        :param progress_builder: A progress builder used to report progress of the
            import.
        :param external_table_fields_to_import: An optional list of fields which should
            also be imported. These fields will be imported into the existing table
            provided in the first item in the tuple, the second being the serialized
            field to import.
            Useful for when importing a single table which also needs to add related
            fields to other existing tables in the database.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :return: The list of created tables
        """

        child_total = self._ops_count_for_import_tables_serialized(
            serialized_tables, external_table_fields_to_import
        )
        progress = ChildProgressBuilder.build(progress_builder, child_total=child_total)

        if "import_workspace_id" not in id_mapping and database.workspace is not None:
            id_mapping["import_workspace_id"] = database.workspace.id

        if "database_tables" not in id_mapping:
            id_mapping["database_tables"] = {}

        if "database_fields" not in id_mapping:
            id_mapping["database_fields"] = {}

        if "database_field_names" not in id_mapping:
            id_mapping["database_field_names"] = {}

        if "workspace_id" not in id_mapping and database.workspace is not None:
            id_mapping["workspace_id"] = database.workspace.id

        # Snapshots will provide a specific workspace to import user references from, so
        # we need to use that instead of the workspace the database is in if provided.
        workspace_for_user_references = (
            import_export_config.workspace_for_user_references
        )
        workspace_id_for_user_references = (
            workspace_for_user_references.id
            if workspace_for_user_references is not None
            else id_mapping.get("workspace_id", None)
        )

        user_email_mapping = {}
        if workspace_id_for_user_references:
            user_email_mapping = CoreHandler.get_user_email_mapping(
                workspace_id_for_user_references, only_emails=[]
            )

        # First, we want to create all the table instances because it could be that
        # field or view properties depend on the existence of a table.
        imported_tables = self._import_tables(
            database, serialized_tables, id_mapping, progress
        )

        deferred_fk_update_collector = DeferredForeignKeyUpdater()
        # Because view properties might depend on fields, we first want to create all
        # the fields. Fields might have dependencies on other fields, so we want to
        # import them in the correct order.
        imported_fields = self._import_table_fields(
            serialized_tables,
            id_mapping,
            import_export_config,
            external_table_fields_to_import,
            deferred_fk_update_collector,
            progress,
        )

        # schema_editor.create_model will also create any m2m/through tables which
        # connect two models together. Once we create_model on the first model
        # the m2m will be made, so if we blindly call create_model on the second
        # model it will crash as the m2m connecting those two models already exists.
        # So instead we keep track of which m2m's have already been made to not
        # make them twice!
        already_created_through_table_names = set()
        # Now that the all tables and fields exist, we can create the views and create
        # the table schema in the database.
        for serialized_table in serialized_tables:
            self._import_table_views(
                serialized_table, import_export_config, id_mapping, files_zip, progress
            )
            self._create_table_schema(
                serialized_table, already_created_through_table_names
            )
            progress.increment(
                state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE}{serialized_table['name']}"
            )

        # Now that everything is in place we can start filling the table with the rows
        # in an efficient matter by using the bulk_create functionality.
        self._import_table_rows(
            serialized_tables,
            imported_fields,
            user_email_mapping,
            deferred_fk_update_collector,
            id_mapping,
            files_zip,
            storage,
            progress,
        )

        # Finally, now that everything has been created, loop over the
        # `serialization_processor_registry` registry and ensure extra
        # metadata is imported too.
        self._import_extra_metadata(serialized_tables, id_mapping, import_export_config)

        self._import_data_sync(serialized_tables, id_mapping, import_export_config)

        self._import_field_rules(serialized_tables, id_mapping, import_export_config)

        return imported_tables

    def _import_extra_metadata(
        self, serialized_tables, id_mapping, import_export_config
    ):
        source_workspace = Workspace.objects.get(pk=id_mapping["import_workspace_id"])
        for serialized_table in serialized_tables:
            table = serialized_table["_object"]
            if not import_export_config.reduce_disk_space_usage:
                SearchHandler.schedule_update_search_data(table)
            for (
                serialized_structure_processor
            ) in serialization_processor_registry.get_all():
                serialized_structure_processor.import_serialized(
                    source_workspace, table, serialized_table, import_export_config
                )

    def _import_data_sync(self, serialized_tables, id_mapping, import_export_config):
        for serialized_table in serialized_tables:
            if not serialized_table.get("data_sync", None):
                continue
            table = serialized_table["_object"]
            serialized_data_sync = serialized_table["data_sync"]
            data_sync_type = data_sync_type_registry.get(serialized_data_sync["type"])
            data_sync_type.import_serialized(
                table, serialized_data_sync, id_mapping, import_export_config
            )

    def _import_field_rules(self, serialized_tables, id_mapping, import_export_config):
        for serialized_table in serialized_tables:
            if not serialized_table.get("field_rules", None):
                continue
            table = serialized_table["_object"]
            field_rules_handler = FieldRuleHandler(table)
            serialized_rules = serialized_table["field_rules"]
            for serialized_rule in serialized_rules:
                field_rules_handler.import_rule(
                    serialized_rule, id_mapping["database_fields"]
                )

    def _import_table_rows(
        self,
        serialized_tables: List[Dict[str, Any]],
        imported_fields: ImportedFields,
        user_email_mapping: Dict[str, Any],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
        id_mapping: Dict[str, Any],
        files_zip: ZipFile | None,
        storage: Storage | None,
        progress: Progress,
    ):
        """
        Imports the rows of a table from the serialized data in an efficient manner.

        :param serialized_tables: The serialized tables to import the rows into.
        :param imported_fields: The imported fields that were created during the import.
        :param user_email_mapping: A mapping of user emails to user instances.
        :param deferred_fk_update_collector: A collector that collects all the foreign
            keys to update them later when the model with all the fields is created.
        :param id_mapping: A mapping of any table ids that might be referenced in
            serialized_tables to their new/existing ids to use in this import.
        :param files_zip: An optional zip of files which can be used to retrieve
            imported files from
        :param storage: An optional place to persist any user files if importing files
            from a the above file_zip.
        :param progress: A progress used to report progress of the import.
        """

        table_cache: Dict[str, Any] = {}
        already_filled_up_through_table_names = set()
        now = datetime.now(tz=timezone.utc)

        for serialized_table in serialized_tables:
            table_model = serialized_table["_model"]
            rows_to_be_inserted = []
            # Holds a mapping where the key is a model, and the value a list of
            # objects that must be inserted. These objects are returned by the
            # `set_import_serialized_value`, and will typically hold m2m relationships.
            additional_objects_to_be_inserted = defaultdict(list)

            m2m_fields_to_not_import_as_already_done = set()
            for field in table_model._meta.get_fields():
                if isinstance(field, models.ManyToManyField):
                    remote_through = field.remote_field.through
                    db_table = remote_through._meta.db_table
                    if db_table in already_filled_up_through_table_names:
                        m2m_fields_to_not_import_as_already_done.add(field.name)
                    else:
                        already_filled_up_through_table_names.add(db_table)

            for serialized_row in serialized_table["rows"]:
                (
                    created_on,
                    updated_on,
                    created_by,
                    last_modified_by,
                ) = self._prepare_base_row_fields(
                    serialized_row, now, user_email_mapping
                )

                row_instance = table_model(
                    id=serialized_row["id"],
                    order=serialized_row["order"],
                    created_on=created_on,
                    updated_on=updated_on,
                    created_by=created_by,
                    last_modified_by=last_modified_by,
                )

                self._import_serialized_fields_values_to_row(
                    row_instance,
                    serialized_row,
                    serialized_table["fields"],
                    table_cache,
                    additional_objects_to_be_inserted,
                    m2m_fields_to_not_import_as_already_done,
                    id_mapping,
                    files_zip,
                    storage,
                )

                rows_to_be_inserted.append(row_instance)
                progress.increment(
                    state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_DATA}{serialized_table['name']}"
                )

            # We want to insert the rows in bulk because there could potentially be
            # hundreds of thousands of rows in there and this will result in better
            # performance.
            for chunk in grouper(512, rows_to_be_inserted):
                table_model.objects.bulk_create(chunk, batch_size=512)
                progress.increment(
                    len(chunk),
                    state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_DATA}{serialized_table['name']}",
                )

            # Every row import can have additional objects that must be inserted,
            # like for example the m2m relationships. We want to efficiently import
            # them in bulk here.
            for model, objects in additional_objects_to_be_inserted.items():
                model.objects.bulk_create(objects, batch_size=512)

            # When the rows are inserted we keep the provide the old ids and because of
            # that the auto increment is still set at `1`. This needs to be set to the
            # maximum value because otherwise creating a new row could later fail.
            sequence_sql = connection.ops.sequence_reset_sql(no_style(), [table_model])
            with connection.cursor() as cursor:
                cursor.execute(sequence_sql[0])

        # Now that the fields have been created, we need to run the deferred fk
        # updates pointing to those.
        deferred_fk_update_collector.run_deferred_fk_updates(
            id_mapping, "database_views"
        )

        # The progress off `apply_updates_and_get_updated_fields` takes 5% of the
        # total progress of this import.
        self._after_rows_imported(imported_fields, progress)

    def _import_serialized_fields_values_to_row(
        self,
        row_instance: GeneratedTableModel,
        serialized_row: Dict[str, Any],
        serialized_table_fields: List[Dict[str, Any]],
        table_cache: Dict[str, Any],
        additional_objects_to_be_inserted: Dict[str, List[object]],
        m2m_fields_to_not_import_as_already_done: Set[str],
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        for serialized_field in serialized_table_fields:
            field_type = field_type_registry.get(serialized_field["type"])
            new_field_id = id_mapping["database_fields"][serialized_field["id"]]
            new_field_name = f"field_{new_field_id}"
            field_name = f'field_{serialized_field["id"]}'

            if (
                field_name in serialized_row
                and new_field_name not in m2m_fields_to_not_import_as_already_done
            ):
                related_objects_to_save = field_type.set_import_serialized_value(
                    row_instance,
                    new_field_name,
                    serialized_row[field_name],
                    id_mapping,
                    table_cache,
                    files_zip,
                    storage,
                )

                if related_objects_to_save is not None:
                    for additional_object in related_objects_to_save:
                        additional_objects_to_be_inserted[
                            additional_object._meta.model
                        ].append(additional_object)

    def _prepare_base_row_fields(
        self,
        serialized_row: Dict[str, Any],
        now: datetime,
        user_email_mapping: Dict[str, Any],
    ) -> Tuple[datetime, datetime, Optional[AbstractUser], Optional[AbstractUser]]:
        """
        Extracts the created_on, updated_on, created_by and last_modified_by fields
        from the serialized row and returns them.

        :param serialized_row: The serialized row to extract the fields from.
        :param now: The current datetime to use for the entire table.
        :param user_email_mapping: A mapping of user emails to user instances.
        :return: A tuple containing the created_on, updated_on, created_by and
            last_modified_by fields.
        """

        created_on = serialized_row.get("created_on")
        updated_on = serialized_row.get("updated_on")

        if created_on:
            created_on = datetime.fromisoformat(created_on)
        else:
            created_on = now

        if updated_on:
            updated_on = datetime.fromisoformat(updated_on)
        else:
            updated_on = now

        created_by_email = serialized_row.get("created_by", None)
        created_by = (
            user_email_mapping.get(created_by_email, None) if created_by_email else None
        )

        last_modified_by_email = serialized_row.get("last_modified_by", None)
        last_modified_by = (
            user_email_mapping.get(last_modified_by_email, None)
            if last_modified_by_email
            else None
        )

        return created_on, updated_on, created_by, last_modified_by

    def _after_rows_imported(
        self,
        imported_fields: ImportedFields,
        progress: Optional[ChildProgressBuilder] = None,
    ):
        """
        Call the `after_rows_imported` method on all fields that have dependencies in
        the correct order. This is necessary because some fields might need to
        recalculate their values after all rows have been imported.

        :param imported_fields: The imported fields that were created during the import.
        :param progress: A progress builder used to report progress of the import.
        """

        # Call the `after_rows_imported` method on all fields in the same order as they
        # were imported, and let the field to immediately update its values if necessary
        # without grouping by table to ensure that the order of the updates is correct.
        for field in (
            imported_fields.fields_without_dependencies
            + imported_fields.fields_with_dependencies
        ):
            field_type = field_type_registry.get_by_model(field)
            field_type.after_rows_imported(
                field, field_cache=imported_fields.field_cache
            )
            progress.increment()

    def _create_table_schema(
        self, serialized_table, already_created_through_table_names
    ):
        table = serialized_table["_object"]

        with safe_django_schema_editor() as schema_editor:
            table_model = table.get_model(
                fields=serialized_table["field_instances"],
                field_ids=[],
                managed=True,
                add_dependencies=False,
            )
            serialized_table["_model"] = table_model
            # We don't need to create all the fields individually because the schema
            # editor can handle the creation of the table schema in one go.
            schema_editor.create_model_tracking_created_m2ms(
                table_model, already_created_through_table_names
            )

            # These field attributes must be disabled for date fields
            # because the export contains correct values and we don't want them
            # to be overwritten when importing.
            date_fields = filter(
                lambda f: isinstance(f, models.DateField),
                serialized_table["_model"]._meta.get_fields(),
            )
            attrs_to_disable_for_import = [
                "auto_now_add",
                "auto_now",
                "sync_with",
                "sync_with_add",
            ]
            for date_field in date_fields:
                for attr in attrs_to_disable_for_import:
                    if getattr(date_field, attr, False):
                        setattr(date_field, attr, False)

            for field_instance in serialized_table["field_instances"]:
                if field_instance.field_constraints.exists():
                    constraints = build_django_field_constraints(
                        field_instance, field_instance.field_constraints.all()
                    )
                    for constraint in constraints:
                        schema_editor.add_constraint(table_model, constraint)

    def _import_table_views(
        self,
        serialized_table: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        progress: Optional[ChildProgressBuilder] = None,
    ) -> None:
        """
        Imports the views of a table from the serialized data.

        :param serialized_table: The serialized table to import the views into.
        :param id_mapping: A mapping of any table ids that might be referenced in
            serialized_table to their new/existing ids to use in this import.
        :param files_zip: An optional zip of files which can be used to retrieve
            imported files from
        :param progress: A progress builder used to report progress of the import.
        """

        table = serialized_table["_object"]
        table_name = serialized_table["name"]
        for serialized_view in serialized_table["views"]:
            view_type = view_type_registry.get(serialized_view["type"])
            view_type.import_serialized(
                table, serialized_view, import_export_config, id_mapping, files_zip
            )
            progress.increment(
                state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE}{table_name}"
            )

    def _import_tables(
        self,
        database: Database,
        serialized_tables: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        progress: Optional[ChildProgressBuilder] = None,
    ) -> List[Table]:
        """
        Import the tables from the serialized data and create the table instances.

        :param database: The database to import the serialized tables into.
        :param serialized_tables: The serialized tables to import.
        :param id_mapping: A mapping of any table ids that might be referenced in
            serialized_tables to their new/existing ids to use in this import.
        :param progress: A progress builder used to report progress of the import.
        :return: The list of created tables
        """

        imported_tables: List[Table] = []

        for serialized_table in serialized_tables:
            table_instance = Table.objects.create(
                database=database,
                name=serialized_table["name"],
                order=serialized_table["order"],
                last_modified_by_column_added=True,
            )
            id_mapping["database_tables"][serialized_table["id"]] = table_instance.id
            serialized_table["_object"] = table_instance
            serialized_table["field_instances"] = []
            imported_tables.append(table_instance)
            table_name = serialized_table["name"]
            progress.increment(
                state=f"{IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE}{table_name}"
            )

        return imported_tables

    def import_serialized(
        self,
        workspace: Workspace,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Imports a database application exported by the `export_serialized` method.
        """

        database_progress, table_progress = 1, len(serialized_values["tables"])
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=database_progress + table_progress
        )

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress.create_child_builder(represents_progress=database_progress),
        )

        database = application.specific
        if serialized_values["tables"]:
            self.import_tables_serialized(
                database,
                serialized_values["tables"],
                id_mapping,
                import_export_config,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=table_progress),
            )

        return database

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related(
            "table_set",
            "table_set__data_sync",
            "table_set__data_sync__synced_properties",
        )

    def enhance_and_filter_queryset(
        self,
        queryset: QuerySet[Database],
        user: AbstractUser,
        workspace: Workspace,
    ) -> QuerySet[Database]:
        tables_qs = Table.objects.select_related(
            "database__workspace", "data_sync"
        ).prefetch_related("data_sync__synced_properties")
        return queryset.prefetch_related(
            Prefetch(
                "table_set",
                queryset=CoreHandler().filter_queryset(
                    user,
                    ListTablesDatabaseTableOperationType.type,
                    tables_qs,
                    workspace=workspace,
                ),
                to_attr="tables",
            ),
        )

    def fetch_tables_to_serialize(
        self, database: Database, user: AbstractUser | None
    ) -> List[Table]:
        """
        Serializes the pages of the builder application, making sure that the user has
        the correct permissions to view them if provided, and fetching the related
        elements and data sources correctly so additional queries are not needed.

        :param builder: The builder application instance.
        :param user: The user trying to access the pages.
        :return: A list of serialized pages that belong to this instance with all
            related elements and data sources fetched correctly.
        """

        base_queryset = Database.objects.filter(id=database.id)

        if user:
            instance = self.enhance_and_filter_queryset(
                base_queryset, user, database.workspace
            ).first()
            return instance and instance.tables or []
        else:
            instance = self.enhance_queryset(base_queryset).first()
            return instance and list(instance.table_set.all()) or []
