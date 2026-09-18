from copy import deepcopy
from typing import List, Optional

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.database.db.atomic import (
    read_committed_single_table_transaction,
)
from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.constants import DeleteFieldStrategyEnum
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.operations import CreateTableDatabaseTableOperationType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.types import CreatedRowsData, UpdatedRowsData
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import UpdateDatabaseTableOperationType
from baserow.contrib.database.table.signals import table_created, table_updated
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.db import specific_queryset
from baserow.core.handler import CoreHandler
from baserow.core.utils import (
    ChildProgressBuilder,
    extract_allowed,
    remove_duplicates,
    set_allowed_attrs,
)

from .constants import BASE_DATA_SYNC_ALLOWED_FIELDS
from .exceptions import (
    DataSyncCredentialRequired,
    DataSyncDoesNotExist,
    PropertyNotFound,
    SyncDataSyncTableAlreadyRunning,
    SyncError,
    TwoWayDataSyncNotSupported,
    UniquePrimaryPropertyNotFound,
)
from .models import DataSync, DataSyncSyncedProperty
from .operations import SyncTableOperationType
from .registries import data_sync_type_registry, two_way_sync_strategy_type_registry

LARGE_DATA_SYNC_SEARCH_UPDATE_MIN_CHANGED_ROWS = 10_000
LARGE_DATA_SYNC_SEARCH_UPDATE_THRESHOLD = 0.5


class DataSyncHandler:
    def _schedule_search_updates_after_sync(
        self,
        data_sync: DataSync,
        enabled_properties: QuerySet[DataSyncSyncedProperty],
        existing_row_count: int,
        created_rows: CreatedRowsData,
        updated_rows: UpdatedRowsData,
        row_ids_to_delete: list[int],
    ) -> None:
        changed_rows_count = (
            len(created_rows.created_rows)
            + len(updated_rows.updated_rows)
            + len(row_ids_to_delete)
        )
        if changed_rows_count == 0:
            return

        search_fields = [p.field for p in enabled_properties]
        full_field_search_update = (
            len(row_ids_to_delete) > 0
            or changed_rows_count > LARGE_DATA_SYNC_SEARCH_UPDATE_MIN_CHANGED_ROWS
            or changed_rows_count
            >= existing_row_count * LARGE_DATA_SYNC_SEARCH_UPDATE_THRESHOLD
        )

        if full_field_search_update:
            SearchHandler.schedule_update_search_data(
                data_sync.table, fields=search_fields
            )
            return

        row_ids_to_refresh = {row.id for row in created_rows.created_rows} | {
            row.id for row in updated_rows.updated_rows
        }
        if created_rows.cascade_update:
            row_ids_to_refresh.update(created_rows.cascade_update.row_ids)
        if updated_rows.cascade_update:
            row_ids_to_refresh.update(updated_rows.cascade_update.row_ids)

        SearchHandler.schedule_update_search_data(
            data_sync.table,
            fields=search_fields,
            row_ids=sorted(row_ids_to_refresh),
        )

    def get_data_sync(
        self, data_sync_id: int, base_queryset: Optional[QuerySet] = None
    ) -> DataSync:
        """
        Returns the data sync matching the provided ID.

        :param data_sync_id: The data sync ID to fetch.
        :param base_queryset: Optionally change the default queryset.
        :return: The fetched data sync object.
        """

        if base_queryset is None:
            base_queryset = DataSync.objects

        try:
            return (
                base_queryset.select_related(
                    "table", "table__database", "table__database__workspace"
                )
                .prefetch_related("synced_properties")
                .get(pk=data_sync_id)
                .specific
            )
        except DataSync.DoesNotExist:
            raise DataSyncDoesNotExist(
                f"Data sync with ID {data_sync_id} does not exist."
            )

    def _get_two_way_sync_strategy_type(self, data_sync_type):
        strategy_type = data_sync_type.two_way_sync_strategy_type
        if not strategy_type:
            raise TwoWayDataSyncNotSupported(
                "Two-way sync is not supported for this data sync type."
            )
        return two_way_sync_strategy_type_registry.get(strategy_type)

    def create_data_sync_table(
        self,
        user: AbstractUser,
        database: Database,
        type_name: str,
        synced_properties: List[str],
        table_name: str,
        **kwargs: dict,
    ) -> DataSync:
        """
        Creates a new data sync, the related table, the synced fields, and will
        immediately sync the data.

        :param user: The user on whose behalf the data sync is created.
        :param database: The database where to create the synced table in.
        :param type_name: The type of the data sync that must be created.
        :param synced_properties: A list of data sync property keys that must be added.
            The primary unique ones are always added.
        :param table_name: The name of the synced table that will be created.
        :raises PropertyNotFound: When the `synced_properties` key is doesn't match a
            property.
        :raises UniquePrimaryPropertyNotFound: When no `unique_primary=True` property
            was returned by the data sync type.
        """

        CoreHandler().check_permissions(
            user,
            CreateTableDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        # Duplicates are not allowed because we can't have two of the same fields
        # that are synced.
        synced_properties = remove_duplicates(synced_properties)

        data_sync_type = data_sync_type_registry.get(type_name)
        model_class = data_sync_type.model_class

        allowed_fields = BASE_DATA_SYNC_ALLOWED_FIELDS + data_sync_type.allowed_fields
        values = extract_allowed(kwargs, allowed_fields)
        values = data_sync_type.prepare_values(user, values)

        # Check if there is two-way support if it must be enabled.
        if values.get("two_way_sync"):
            two_way_sync_strategy = self._get_two_way_sync_strategy_type(data_sync_type)
            two_way_sync_strategy.before_enable(database.workspace)

        # Create an empty table where we're going to sync the data into, and add it to
        # the values, so that it already can be used in the `get_properties` method.
        last_order = Table.get_last_order(database)
        table = Table.objects.create(
            database=database, order=last_order, name=table_name
        )
        values["table"] = table

        data_sync_instance = model_class(**values)
        data_sync_properties = data_sync_type.get_properties(data_sync_instance)

        # The unique primary properties must always be added to the table because
        # it's used for identification purposes.
        for data_sync_property in data_sync_properties:
            if (
                data_sync_property.unique_primary
                and data_sync_property.key not in synced_properties
            ):
                synced_properties.insert(0, data_sync_property.key)

        data_sync_instance.save()

        properties_to_create = []
        has_primary = False
        field_handler = FieldHandler()
        for index, synced_property in enumerate(synced_properties):
            data_sync_property = next(
                (p for p in data_sync_properties if p.key == synced_property), None
            )
            if not data_sync_property:
                raise PropertyNotFound(
                    synced_property,
                    f"The property {synced_property} is not found in "
                    f"{data_sync_type.type}.",
                )

            baserow_field = data_sync_property.to_baserow_field()
            baserow_field.name = field_handler.find_next_unused_field_name(
                table,
                [baserow_field.name],
            )
            baserow_field.order = index
            baserow_field.table = table
            baserow_field.read_only = (
                data_sync_property.unique_primary or not values.get("two_way_sync")
            )
            baserow_field.immutable_type = True
            baserow_field.immutable_properties = data_sync_property.immutable_properties
            if data_sync_property.unique_primary and not has_primary:
                has_primary = True
                baserow_field.primary = True
            baserow_field.save()
            metadata = data_sync_property.get_metadata(baserow_field)

            properties_to_create.append(
                DataSyncSyncedProperty(
                    data_sync=data_sync_instance,
                    field=baserow_field,
                    key=synced_property,
                    unique_primary=data_sync_property.unique_primary,
                    metadata=metadata,
                )
            )

        if not has_primary:
            raise UniquePrimaryPropertyNotFound(
                "The data sync `data_sync_type.type` didn't return a unique_primary "
                "property."
            )

        DataSyncSyncedProperty.objects.bulk_create(properties_to_create)

        # Create default view.
        with translation.override(user.profile.language):
            ViewHandler().create_view(user, table, GridViewType.type, name=_("Grid"))

        # Create the table schema in the database.
        with safe_django_schema_editor() as schema_editor:
            # Django only creates indexes when the model is managed.
            model = table.get_model(managed=True)
            schema_editor.create_model(model)

        table_created.send(self, table=table, user=user)

        return data_sync_instance

    def update_data_sync_table(
        self,
        user: AbstractUser,
        data_sync: DataSync,
        synced_properties: List[str],
        **kwargs: dict,
    ) -> DataSync:
        """
        Updates the synced properties and data sync properties.

        :param user: The user on whose behalf the data sync is updated.
        :param data_sync: The data sync that must be updated.
        :param synced_properties: A list of all properties that must be in data sync
            table. New ones will be created, and removed ones will be deleted.
        :return: The updated data sync.
        """

        CoreHandler().check_permissions(
            user,
            UpdateDatabaseTableOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )

        data_sync = data_sync.specific
        data_sync_type = data_sync_type_registry.get_by_model(data_sync)

        allowed_fields = BASE_DATA_SYNC_ALLOWED_FIELDS + data_sync_type.allowed_fields

        # Check if there is two-way support, if it must be enabled and wasn't enabled
        # before.
        if "two_way_sync" in kwargs and kwargs["two_way_sync"]:
            two_way_sync_strategy = self._get_two_way_sync_strategy_type(data_sync_type)
            two_way_sync_strategy.before_enable(data_sync.table.database.workspace)
            if not data_sync.two_way_sync:
                # If the two-way sync is enabled, but wasn't before, then reset the
                # number of consecutive failures because the user could have fixed the
                # problem after it was automatically disabled.
                data_sync.two_way_sync_consecutive_failures = 0

        for (
            secret_field,
            target_fields,
        ) in data_sync_type.secret_field_dependencies.items():
            target_changed = any(
                field in kwargs and kwargs[field] != getattr(data_sync, field)
                for field in target_fields
            )
            if target_changed and secret_field not in kwargs:
                raise DataSyncCredentialRequired(
                    "When changing the connection target, the credential must be "
                    "re-supplied."
                )

        data_sync = set_allowed_attrs(kwargs, allowed_fields, data_sync)
        data_sync.save()

        data_sync_properties = data_sync_type.get_properties(data_sync)
        data_sync_property_keys = [p.key for p in data_sync_properties]
        # Omit properties that are not available anymore to prevent the backend from
        # failing hard.
        synced_properties = [
            p for p in synced_properties if p in data_sync_property_keys
        ]

        self.set_data_sync_synced_properties(
            user,
            data_sync,
            synced_properties=synced_properties,
            data_sync_properties=data_sync_properties,
        )

        table_updated.send(
            self, table=data_sync.table, user=user, force_table_refresh=False
        )

        return data_sync

    def get_table_sync_lock_key(self, data_sync_id):
        return f"data_sync_{data_sync_id}_syncing_table"

    def sync_data_sync_table(
        self,
        user: AbstractUser,
        data_sync: DataSync,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> DataSync:
        """
        Synchronizes the table with the data sync. This will automatically create
        missing rows, update existing rows, and delete rows that no longer exist. There
        can only be one data sync active at the same time to avoid conflicts.

        :param user: The user on whose behalf the data sync is triggered.
        :param data_sync: The data sync object that must be synced.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :raises SyncDataSyncTableAlreadyRunning: if the data sync table is already
            being synced. Only one can run concurrently.
        :return:
        """

        CoreHandler().check_permissions(
            user,
            SyncTableOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )

        try:
            lock_key = self.get_table_sync_lock_key(data_sync.id)
            lock_acquired = cache.add(lock_key, "locked", timeout=2)

            if not lock_acquired:
                raise SyncDataSyncTableAlreadyRunning(
                    f"Sync data sync table of data sync {data_sync.id} is already"
                    f"running"
                )

            try:
                self._do_sync_table(user, data_sync, progress_builder)
            finally:
                cache.delete(lock_key)
        # If calling `get_all_rows` fails with a `SyncError`, then it's an expected
        # error, and it shouldn't fail hard. We do want to store the error in the
        # database to expose via the API.
        except SyncError as e:
            data_sync.last_error = str(e)
            data_sync.save(update_fields=("last_error",))
            return data_sync

        data_sync.last_sync = timezone.now()
        data_sync.last_error = None
        data_sync.save(
            update_fields=(
                "last_sync",
                "last_error",
            )
        )

        table_updated.send(
            self, table=data_sync.table, user=user, force_table_refresh=True
        )

        return data_sync

    def _do_sync_table(self, user, data_sync, progress_builder):
        progress = ChildProgressBuilder.build(progress_builder, 100)

        data_sync_type = data_sync_type_registry.get_by_model(data_sync)
        data_sync_type.before_sync_table(user, data_sync)
        all_properties = data_sync_type.get_properties(data_sync)
        key_to_property = {p.key: p for p in all_properties}
        progress.increment(by=1)

        # Before doing anything we would need to run the
        # `set_data_sync_synced_properties` with the same visible properties. This is
        # because data sync type properties might have changed, and we want to make sure
        # they're in sync before syncing the rows.
        enabled_properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
        if data_sync.auto_add_new_properties:
            # If `auto_add_new_properties` is true, then we always want to enable all
            # the properties of the data sync. This automatically adds new ones.
            flat_enabled_properties = key_to_property
        else:
            flat_enabled_properties = [
                key
                for key in enabled_properties.values_list("key", flat=True)
                if key in key_to_property.keys()
            ]
        # --- Schema phase (inside its own transaction) ---
        # This must run before the fetch: `get_all_rows` maps the source values onto
        # the fields and select options this creates, so fetching first would produce
        # rows referring to select options that no longer exist. It gets its own
        # transaction so that a failure part-way through doesn't half-apply the DDL.
        #
        # Because the fetch that follows is deliberately not in a transaction, this
        # one has already committed by the time a later phase can fail, so it can't
        # be rolled back. The fields it added are therefore removed explicitly below
        # if anything after this point fails, which would otherwise leave empty
        # columns behind on a table that never received the matching rows.
        #
        # Additive only: removing a property permanently deletes its column, so a
        # failed fetch would destroy data. Deferred until the rows are written.
        with transaction.atomic():
            added_field_ids = self.set_data_sync_synced_properties(
                user,
                data_sync,
                synced_properties=flat_enabled_properties,
                data_sync_properties=all_properties,
                remove_obsolete_properties=False,
            )
        progress.increment(by=1)

        try:
            self._fetch_and_write_rows(
                user,
                data_sync,
                data_sync_type,
                all_properties,
                progress,
            )
        except Exception:
            # The schema phase has already committed (see above), so its fields are
            # removed here rather than rolled back. Without this a failed sync leaves
            # empty columns behind on a table that never received the matching rows.
            self._remove_fields_added_by_failed_sync(user, data_sync, added_field_ids)
            raise

        # The deferred removal. A failure here leaves an obsolete column, which the
        # next sync removes; deleting it before the fetch succeeded is permanent.
        with transaction.atomic():
            self.set_data_sync_synced_properties(
                user,
                data_sync,
                synced_properties=flat_enabled_properties,
                data_sync_properties=all_properties,
            )

    def _remove_fields_added_by_failed_sync(self, user, data_sync, added_field_ids):
        """
        Deletes the fields that the schema phase of a failed sync created, so the
        table is left at the schema it had before that sync started.

        There is nothing to restore: the schema phase only adds, and the removal of
        properties the source no longer reports is deferred until after the rows are
        written, so a run that failed never deleted a field to begin with.

        Two conditions must both hold before a field is deleted, because the
        deletion is permanent and takes the column's data with it:

        1. The field is in `added_field_ids` -- the exact set of fields *this* run
           created, as returned by `set_data_sync_synced_properties`. Fields that
           existed before this run are never touched.
        2. The field's column is still empty. This run never got as far as writing
           rows, so a field it created can only hold data if something else put it
           there. That happens when a second sync starts while this one is between
           its schema phase and its write phase -- the sync lock is only held for a
           couple of seconds and is never refreshed -- and adopts the fields this
           run created rather than creating its own. Deleting those would destroy
           the other sync's data.

        `last_sync` is deliberately not used to detect that case: it is only
        written on success, so two overlapping syncs that both fail, and any
        initial sync where it is `None` throughout, compare equal and the check
        passes exactly when it matters most.

        Never raises: the caller is already handling a failure, and losing the
        original error to a cleanup problem would hide why the sync failed.
        """

        if not added_field_ids:
            return

        try:
            with transaction.atomic():
                field_handler = FieldHandler()
                properties = DataSyncSyncedProperty.objects.filter(
                    data_sync=data_sync, field_id__in=added_field_ids
                ).select_related("field")
                fields = [p.field for p in properties]
                if not fields:
                    return

                # Under READ COMMITTED a concurrent sync could commit rows between
                # the check below and `delete_field`, dropping a populated column.
                self._lock_table_rows(data_sync.table)

                populated_field_ids = self._get_populated_field_ids(
                    data_sync.table, fields
                )
                fields_to_delete = [
                    field for field in fields if field.id not in populated_field_ids
                ]
                if populated_field_ids:
                    logger.warning(
                        f"Not removing {len(populated_field_ids)} field(s) added by "
                        f"the failed sync of data sync {data_sync.id} because they "
                        f"now contain data, most likely written by a sync that "
                        f"started while this one was in flight: "
                        f"{sorted(populated_field_ids)}."
                    )
                if not fields_to_delete:
                    return

                DataSyncSyncedProperty.objects.filter(
                    data_sync=data_sync,
                    field_id__in=[field.id for field in fields_to_delete],
                ).delete()
                for field in fields_to_delete:
                    field_handler.delete_field(
                        user=user,
                        field=field,
                        allow_deleting_primary=True,
                        delete_strategy=DeleteFieldStrategyEnum.PERMANENTLY_DELETE,
                    )
        except Exception:
            logger.exception(
                f"Failed to remove the fields added by the failed sync of data sync "
                f"{data_sync.id}. The table may be left with empty columns."
            )

    def _lock_table_rows(self, table):
        """
        Blocks concurrent writes to the table for the rest of the surrounding
        transaction. `SHARE` is the weakest mode conflicting with the
        `ROW EXCLUSIVE` every write takes, so readers are unaffected.

        Never raises: the caller is already handling a failure, and a lock that
        can't be taken must not replace the original error.
        """

        try:
            model = table.get_model()
            with connection.cursor() as cursor:
                cursor.execute(
                    f'LOCK TABLE "{model._meta.db_table}" IN SHARE MODE'  # nosec B608
                )
        except Exception:
            logger.exception(
                f"Could not lock the rows of table {table.id} before removing the "
                f"fields added by a failed sync. Continuing without the lock."
            )

    def _get_populated_field_ids(self, table, fields):
        """
        Returns the ids of the given fields whose column holds a value in at least
        one row, so the caller can avoid permanently deleting a field that carries
        data.

        Errs on the side of caution: if the check itself can't be made, every field
        is reported as populated so that nothing is deleted.
        """

        try:
            model = table.get_model()
            field_names = {field.id: f"field_{field.id}" for field in fields}
            populated = set()
            # A text column stores "" rather than NULL, so `NOT NULL` alone
            # matches every row. Push the "" and [] halves into SQL where the
            # column type allows it and take one row; whatever comes back is
            # judged in Python, so falsy-but-real values (False, 0, rating 0)
            # still count as populated.
            for field_id, field_name in field_names.items():
                base_queryset = model.objects.filter(~Q(**{field_name: None}))
                for empty_value in ("", []):
                    # Not every column type can be compared against both; when
                    # it can't, that half falls through to the Python check.
                    try:
                        base_queryset = base_queryset.exclude(
                            **{field_name: empty_value}
                        )
                    except Exception:
                        pass
                # LIMIT 1: only existence matters, never how many.
                row = base_queryset.values(field_name)[:1].first()
                if row is not None and row[field_name] not in (None, "", []):
                    populated.add(field_id)
            return populated
        except Exception:
            logger.exception(
                f"Could not determine whether the fields added by the failed sync "
                f"of table {table.id} contain data. Assuming they do, so none of "
                f"them are deleted."
            )
            return {field.id for field in fields}

    def _fetch_and_write_rows(
        self, user, data_sync, data_sync_type, all_properties, progress
    ):
        unique_primary_keys = [p.key for p in all_properties if p.unique_primary]

        # State of the rows that existed before any remote I/O started.
        #
        # The ids are used by the delete phase to tell a row the source dropped
        # apart from one a user created while the fetch was in flight.
        #
        # The synced cell values are used by the update phase to detect cells a
        # user changed *during* the fetch. Comparing values per cell rather than
        # using the row's `updated_on` keeps the check narrow: an edit to a column
        # the sync doesn't own must not hold back a change to one it does.
        #
        # This is deliberately a second copy of the same columns the write phase
        # re-reads: this one is the state *before* the fetch, that one the state
        # *now*, and the difference between them is exactly what identifies a
        # concurrent edit. It selects only `id` plus the synced columns, so the
        # width is already the minimum the comparison needs.
        pre_fetch_model = data_sync.table.get_model()
        pre_fetch_enabled_properties = DataSyncSyncedProperty.objects.filter(
            data_sync=data_sync
        )
        pre_fetch_field_names = [
            f"field_{p.field_id}" for p in pre_fetch_enabled_properties
        ]
        pre_fetch_rows = {
            row["id"]: row
            for row in pre_fetch_model.objects.all().values(
                *["id"] + pre_fetch_field_names
            )
        }
        pre_fetch_row_ids = set(pre_fetch_rows.keys())

        # --- Fetch phase (outside transaction) ---
        # HTTP calls to external services (Jira, GitHub, etc.) happen here so that the
        # database transaction is not held open for the duration of potentially slow
        # network I/O.
        rows_of_data_sync = {
            tuple(row[key] for key in unique_primary_keys): row
            for row in data_sync_type.get_all_rows(
                data_sync,
                progress_builder=progress.create_child_builder(represents_progress=56),
            )
        }
        # The keys the rows were actually fetched with, for the write phase below.
        fetched_property_keys = set().union(
            *[row.keys() for row in rows_of_data_sync.values()] or [set()]
        )

        # --- Write phase (inside READ COMMITTED transaction) ---
        # Re-read schema and existing rows under the field/table lock so the diff is
        # computed against a schema that can't change underneath it.
        with read_committed_single_table_transaction(data_sync.table_id):
            model = data_sync.table.get_model()
            # Fetch the data sync properties again because they could have been changed
            # after calling `set_data_sync_synced_properties`.
            key_to_property = {p.key: p for p in all_properties}
            # The properties can have changed during the fetch: one enabled since
            # has no value in the fetched rows, one the source dropped is still
            # enabled here because its removal is deferred. Both would `KeyError`.
            # The next sync fetches with the first; the second is removed below.
            enabled_properties = [
                p
                for p in DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
                if p.key in fetched_property_keys and p.key in key_to_property
            ]
            key_to_field_id = {p.key: f"field_{p.field_id}" for p in enabled_properties}
            progress.increment(by=1)

            existing_rows_queryset = model.objects.all().values(
                *["id"] + list(key_to_field_id.values())
            )
            progress.increment(by=6)

            existing_rows_in_table = {
                tuple(row[key_to_field_id[key]] for key in unique_primary_keys): row
                for row in existing_rows_queryset
                if all(row[key_to_field_id[key]] for key in unique_primary_keys)
            }
            progress.increment(by=2)

            rows_to_create = []
            for new_id, data in rows_of_data_sync.items():
                if new_id not in existing_rows_in_table:
                    rows_to_create.append(
                        {
                            f"field_{property.field_id}": data[property.key]
                            for property in enabled_properties
                        }
                    )
            progress.increment(by=1)

            rows_to_update = []
            for existing_id, existing_record in existing_rows_in_table.items():
                if existing_id in rows_of_data_sync:
                    new_record_data = rows_of_data_sync[existing_id]
                    row_id = existing_record["id"]
                    pre_fetch_row = pre_fetch_rows.get(row_id)
                    changed = False
                    for enabled_property in enabled_properties:
                        key = enabled_property.key
                        value = new_record_data[key]
                        field_name = key_to_field_id[key]
                        baserow_row_value = existing_record[field_name]
                        data_sync_property = key_to_property[key]
                        if data_sync_property.is_equal(baserow_row_value, value):
                            continue

                        # A cell whose Baserow value moved since the fetch started
                        # was edited while the source was being read, so the value
                        # in hand predates that edit. For a two-way sync the edit
                        # has already been pushed to the source, which means
                        # writing the fetched value would overwrite current state
                        # with an older read of the same source. The cell is left
                        # alone; the next sync reads the source after the push and
                        # settles it. Rows created during the fetch have no
                        # pre-fetch value and are written normally.
                        if (
                            pre_fetch_row is not None
                            and field_name in pre_fetch_row
                            and not data_sync_property.is_equal(
                                pre_fetch_row[field_name], baserow_row_value
                            )
                        ):
                            logger.warning(
                                f"Data sync {data_sync.id} skipped writing property "
                                f"'{key}' of row {row_id} in table "
                                f"{data_sync.table_id} (field "
                                f"{enabled_property.field_id}) because the cell "
                                f"changed in Baserow while the source was being "
                                f"read. Kept the current value "
                                f"{baserow_row_value!r} instead of the fetched "
                                f"value {value!r}."
                            )
                            continue

                        existing_record[field_name] = value
                        changed = True
                    if changed:
                        rows_to_update.append(existing_record)
            progress.increment(by=2)

            row_ids_to_delete = []
            if data_sync.delete_unmatched_rows:
                for existing_id in existing_rows_in_table.keys():
                    if existing_id is None or existing_id not in rows_of_data_sync:
                        row_ids_to_delete.append(
                            existing_rows_in_table[existing_id]["id"]
                        )
                for row in existing_rows_queryset:
                    if any(
                        not row[key_to_field_id[key]] for key in unique_primary_keys
                    ):
                        row_ids_to_delete.append(row["id"])
                # Rows that did not exist when the fetch started can't be missing
                # from the source; they were created by a user in the meantime.
                row_ids_to_delete = [
                    row_id
                    for row_id in row_ids_to_delete
                    if row_id in pre_fetch_row_ids
                ]
            progress.increment(by=1)

            created_rows = CreatedRowsData([], {}, [], None)
            if len(rows_to_create) > 0:
                created_rows = RowHandler().create_rows(
                    user=user,
                    table=data_sync.table,
                    model=model,
                    rows_values=rows_to_create,
                    generate_error_report=False,
                    send_realtime_update=False,
                    send_webhook_events=False,
                    skip_search_update=True,
                    signal_params={"skip_two_way_sync": True},
                )
            progress.increment(by=10)

            updated_rows = UpdatedRowsData([], [], {}, {}, None, [], None)
            if len(rows_to_update) > 0:
                updated_rows = RowHandler().update_rows(
                    user=user,
                    table=data_sync.table,
                    rows_values=rows_to_update,
                    model=model,
                    send_realtime_update=False,
                    send_webhook_events=False,
                    skip_search_update=True,
                    signal_params={"skip_two_way_sync": True},
                )
            progress.increment(by=10)

            if len(row_ids_to_delete) > 0:
                RowHandler().delete_rows(
                    user=user,
                    table=data_sync.table,
                    row_ids=row_ids_to_delete,
                    model=model,
                    send_realtime_update=False,
                    send_webhook_events=False,
                    permanently_delete=True,
                    signal_params={"skip_two_way_sync": True},
                )
            progress.increment(by=10)

            self._schedule_search_updates_after_sync(
                data_sync=data_sync,
                enabled_properties=enabled_properties,
                existing_row_count=len(existing_rows_queryset),
                created_rows=created_rows,
                updated_rows=updated_rows,
                row_ids_to_delete=row_ids_to_delete,
            )

    def set_data_sync_synced_properties(
        self,
        user: Optional[AbstractUser],
        data_sync: DataSync,
        synced_properties: List[str],
        data_sync_properties: Optional[List[DataSyncSyncedProperty]] = None,
        remove_obsolete_properties: bool = True,
    ) -> List[int]:
        """
        Changes the properties that are visible in the synced table. If a visible
        property is removed from the list, then it will be removed from the table. If
        a new property is added, the field will be created.

        :param user: The user on whose behalf the properties are updated.
        :param data_sync: The data sync of which the properties must be updated.
        :param synced_properties: A list of all properties that must be in data sync
            table. New ones will be created, and removed ones will be deleted.
        :param data_sync_properties: If the data sync properties have already been
            fetched, they can be provided as argument to avoid fetching them again.
        :param remove_obsolete_properties: Whether properties no longer in
            `synced_properties` are removed. That permanently deletes their column
            and cannot be rolled back, so a caller with fallible work left passes
            `False` and calls again with `True` once that work succeeded.
        :return: The ids of the fields that were newly created, so that a caller that
            fails later on can remove them again.
        """

        # Remove the web_socket_id, so that the client receives the real-time messages
        # when a field is created or deleted. These fields are not exposed to the user
        # when making the API call, so this informs the user about those changes.
        user = deepcopy(user)
        user.web_socket_id = None

        # No need to do a permission check because that's handled in the FieldHandler
        # create and delete methods.

        # Duplicates are not allowed because we can't have two of the same fields
        # that are synced.
        synced_properties = remove_duplicates(synced_properties)
        data_sync_type = data_sync_type_registry.get_by_model(data_sync)

        # If the `data_sync_properties` have been provided, then it's because they've
        # already been fetched, and there is no need to do that for a second time.
        if data_sync_properties is None:
            data_sync_properties = data_sync_type.get_properties(data_sync)

        for data_sync_property in data_sync_properties:
            if (
                data_sync_property.unique_primary
                and data_sync_property.key not in synced_properties
            ):
                synced_properties.insert(0, data_sync_property.key)

        enabled_properties = DataSyncSyncedProperty.objects.filter(
            data_sync=data_sync,
        ).prefetch_related(
            # Deliberately using the trashed fields. They still synced because the
            # user has the ability to restore them.
            Prefetch(
                "field", queryset=specific_queryset(Field.objects_and_trash.all())
            ),
            "field__select_options",
        )
        enabled_properties_per_key = {p.key: p for p in enabled_properties}
        enabled_property_keys = enabled_properties_per_key.keys()
        properties_to_be_removed = []
        properties_to_be_updated = []
        properties_to_be_added = []

        for synced_property in synced_properties:
            data_sync_property = next(
                (p for p in data_sync_properties if p.key == synced_property), None
            )
            if not data_sync_property:
                raise PropertyNotFound(
                    f"The property {synced_property} is not found in "
                    f"{data_sync_type.type}."
                )
            if synced_property not in enabled_property_keys:
                properties_to_be_added.append(data_sync_property)
            elif synced_property in enabled_property_keys:
                enabled_property = enabled_properties_per_key[synced_property]
                existing_field_class = enabled_property.field.specific_class
                new_field = data_sync_property.to_baserow_field()

                existing_metadata = enabled_property.metadata
                new_metadata = data_sync_property.get_metadata(
                    enabled_property.field, existing_metadata
                )

                # If the field type, immutable_properties or unique_primary has changed,
                # then the field must be updated.
                if (
                    not isinstance(new_field, existing_field_class)
                    or data_sync_property.immutable_properties
                    != enabled_property.field.immutable_properties
                    or (data_sync_property.unique_primary or not data_sync.two_way_sync)
                    != enabled_property.field.read_only
                    or data_sync_property.unique_primary
                    != enabled_property.unique_primary
                    # If the metadata has changed, then the field must be updated
                    # because the metadata is updated there. This is for example used
                    # in the local Baserow data sync to map the select option cell
                    # values.
                    or existing_metadata != new_metadata
                ):
                    properties_to_be_updated.append((data_sync_property, new_metadata))

        if remove_obsolete_properties:
            for enabled_property in enabled_properties:
                if enabled_property.key not in synced_properties:
                    properties_to_be_removed.append(enabled_property)

        handler = FieldHandler()

        # A renamed primary key leaves both properties `unique_primary` here, so
        # skip the one being deleted or the table ends up without a primary field.
        removed_field_ids = {p.field_id for p in properties_to_be_removed}
        unique_primary_field = next(
            (
                ep.field
                for ep in enabled_properties
                if ep.unique_primary and ep.field_id not in removed_field_ids
            ),
            None,
        )

        for data_sync_property_instance in properties_to_be_removed:
            field = data_sync_property_instance.field
            # If we're about to delete the primary field, first move primary to the
            # unique_primary field so the table is never left without one.
            if (
                field.primary
                and unique_primary_field
                and unique_primary_field.id != field.id
            ):
                handler.change_primary_field(
                    user=user,
                    table=data_sync.table,
                    new_primary_field=unique_primary_field,
                )
            data_sync_property_instance.delete()
            handler.delete_field(
                user=user,
                field=field,
                allow_deleting_primary=True,
                delete_strategy=DeleteFieldStrategyEnum.PERMANENTLY_DELETE,
            )

        has_primary = data_sync.table.field_set.filter(primary=True).exists()

        added_field_ids = []

        for data_sync_property in properties_to_be_added:
            baserow_field = data_sync_property.to_baserow_field()
            baserow_field_type = field_type_registry.get_by_model(baserow_field)
            field_kwargs = baserow_field.__dict__
            field_kwargs["read_only"] = (
                data_sync_property.unique_primary or not data_sync.two_way_sync
            )
            field_kwargs["immutable_type"] = True
            field_kwargs["immutable_properties"] = (
                data_sync_property.immutable_properties
            )
            if data_sync_property.unique_primary and not has_primary:
                has_primary = True
                field_kwargs["primary"] = True
            # It could be that a field with the same name already exists. In that case,
            # we don't want to block the creation of the field, but rather find a name
            # that works.
            new_name = handler.find_next_unused_field_name(
                data_sync.table,
                [field_kwargs.pop("name")],
            )
            field = handler.create_field(
                user=user,
                table=data_sync.table,
                type_name=baserow_field_type.type,
                name=new_name,
                **field_kwargs,
            )
            metadata = data_sync_property.get_metadata(field)
            DataSyncSyncedProperty.objects.create(
                data_sync=data_sync,
                field=field,
                key=data_sync_property.key,
                unique_primary=data_sync_property.unique_primary,
                metadata=metadata,
            )
            added_field_ids.append(field.id)

        for data_sync_property, new_metadata in properties_to_be_updated:
            enabled_property = enabled_properties_per_key[data_sync_property.key]
            baserow_field = data_sync_property.to_baserow_field()
            baserow_field_type = field_type_registry.get_by_model(baserow_field)
            field_kwargs = baserow_field.__dict__
            field_kwargs["read_only"] = (
                data_sync_property.unique_primary or not data_sync.two_way_sync
            )
            field_kwargs["immutable_type"] = True
            field_kwargs["immutable_properties"] = (
                data_sync_property.immutable_properties
            )
            enabled_property.field = handler.update_field(
                user=user,
                field=enabled_property.field.specific,
                new_type_name=baserow_field_type.type,
                **field_kwargs,
            )
            enabled_property.unique_primary = data_sync_property.unique_primary
            enabled_property.metadata = new_metadata
            enabled_property.save(
                update_fields=(
                    "unique_primary",
                    "metadata",
                )
            )

        return added_field_ids
