from copy import deepcopy
from typing import List, Optional

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db.models import Prefetch, QuerySet
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.constants import DeleteFieldStrategyEnum
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.operations import CreateTableDatabaseTableOperationType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.types import CreatedRowsData
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

from .exceptions import (
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


class DataSyncHandler:
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

        allowed_fields = [
            "auto_add_new_properties",
            "two_way_sync",
        ] + data_sync_type.allowed_fields
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

        allowed_fields = [
            "auto_add_new_properties",
            "two_way_sync",
        ] + data_sync_type.allowed_fields

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
        self.set_data_sync_synced_properties(
            user,
            data_sync,
            synced_properties=flat_enabled_properties,
            data_sync_properties=all_properties,
        )
        progress.increment(by=1)  # makes the total `1`

        model = data_sync.table.get_model()
        unique_primary_keys = [p.key for p in all_properties if p.unique_primary]
        # Fetch the data sync properties again because they could have been changed
        # after calling `set_data_sync_synced_properties`.
        enabled_properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
        key_to_field_id = {p.key: f"field_{p.field_id}" for p in enabled_properties}
        key_to_property = {p.key: p for p in all_properties}
        progress.increment(by=1)  # makes the total `2`

        existing_rows_queryset = model.objects.all().values(
            # There is no need to fetch the rows cell values from the row because we
            # don't need them.
            *["id"]
            + list(key_to_field_id.values())
        )
        progress.increment(by=6)  # makes the total `9`

        existing_rows_in_table = {
            tuple(row[key_to_field_id[key]] for key in unique_primary_keys): row
            for row in existing_rows_queryset
            # Unique primaries can't be empty. If they are, then they're left dangling
            # because the primary was removed. They will be deleted later.
            if all(row[key_to_field_id[key]] for key in unique_primary_keys)
        }
        progress.increment(by=1)  # makes the total `10`

        rows_of_data_sync = {
            tuple(row[key] for key in unique_primary_keys): row
            for row in data_sync_type.get_all_rows(
                data_sync,
                progress_builder=progress.create_child_builder(
                    represents_progress=56  # makes the total `66`
                ),
            )
        }

        rows_to_create = []
        for new_id, data in rows_of_data_sync.items():
            if new_id not in existing_rows_in_table:
                rows_to_create.append(
                    {
                        f"field_{property.field_id}": data[property.key]
                        for property in enabled_properties
                    }
                )
        progress.increment(by=1)  # makes the total `67`

        rows_to_update = []
        for existing_id, existing_record in existing_rows_in_table.items():
            if existing_id in rows_of_data_sync:
                new_record_data = rows_of_data_sync[existing_id]
                changed = False
                for enabled_property in enabled_properties:
                    key = enabled_property.key
                    value = new_record_data[key]
                    baserow_row_value = existing_record[key_to_field_id[key]]
                    data_sync_property = key_to_property[key]
                    if not data_sync_property.is_equal(baserow_row_value, value):
                        existing_record[key_to_field_id[key]] = value
                        changed = True
                if changed:
                    rows_to_update.append(existing_record)
        progress.increment(by=2)  # makes the total `69`

        row_ids_to_delete = []
        for existing_id in existing_rows_in_table.keys():
            if existing_id is None or existing_id not in rows_of_data_sync:
                row_ids_to_delete.append(existing_rows_in_table[existing_id]["id"])
        # Loop over the dangling rows and delete those because they can't be identified
        # anymore.
        for row in existing_rows_queryset:
            if any(not row[key_to_field_id[key]] for key in unique_primary_keys):
                row_ids_to_delete.append(row["id"])
        progress.increment(by=1)  # makes the total `70`

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
        progress.increment(by=10)  # makes the total `80`

        if len(rows_to_update) > 0:
            RowHandler().update_rows(
                user=user,
                table=data_sync.table,
                rows_values=rows_to_update,
                model=model,
                send_realtime_update=False,
                send_webhook_events=False,
                skip_search_update=True,
                signal_params={"skip_two_way_sync": True},
            )
        progress.increment(by=10)  # makes the total `90`

        if len(row_ids_to_delete) > 0:
            RowHandler().delete_rows(
                user=user,
                table=data_sync.table,
                row_ids=row_ids_to_delete,
                model=model,
                send_realtime_update=False,
                send_webhook_events=False,
                # The rows should not be trashed
                permanently_delete=True,
                signal_params={"skip_two_way_sync": True},
            )
        progress.increment(by=10)  # makes the total `100`

        if (
            len(rows_to_create) > 0
            or len(rows_to_update) > 0
            or len(row_ids_to_delete) > 0
        ):
            # No need to include this in the progress as it triggers a celery task
            row_ids = [r["id"] for r in rows_to_update] + [
                r.id for r in created_rows.created_rows
            ]
            SearchHandler.schedule_update_search_data(
                data_sync.table,
                fields=[p.field for p in enabled_properties],
                row_ids=row_ids,
            )

    def set_data_sync_synced_properties(
        self,
        user: Optional[AbstractUser],
        data_sync: DataSync,
        synced_properties: List[str],
        data_sync_properties: Optional[List[DataSyncSyncedProperty]] = None,
    ):
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

        for enabled_property in enabled_properties:
            if enabled_property.key not in synced_properties:
                properties_to_be_removed.append(enabled_property)

        handler = FieldHandler()

        for data_sync_property_instance in properties_to_be_removed:
            field = data_sync_property_instance.field
            data_sync_property_instance.delete()
            handler.delete_field(
                user=user,
                field=field,
                allow_deleting_primary=True,
                delete_strategy=DeleteFieldStrategyEnum.PERMANENTLY_DELETE,
            )

        has_primary = data_sync.table.field_set.filter(primary=True).exists()

        for data_sync_property in properties_to_be_added:
            baserow_field = data_sync_property.to_baserow_field()
            baserow_field_type = field_type_registry.get_by_model(baserow_field)
            field_kwargs = baserow_field.__dict__
            field_kwargs["read_only"] = (
                data_sync_property.unique_primary or not data_sync.two_way_sync
            )
            field_kwargs["immutable_type"] = True
            field_kwargs[
                "immutable_properties"
            ] = data_sync_property.immutable_properties
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
            print(new_name)
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

        for data_sync_property, new_metadata in properties_to_be_updated:
            enabled_property = enabled_properties_per_key[data_sync_property.key]
            baserow_field = data_sync_property.to_baserow_field()
            baserow_field_type = field_type_registry.get_by_model(baserow_field)
            field_kwargs = baserow_field.__dict__
            field_kwargs["read_only"] = (
                data_sync_property.unique_primary or not data_sync.two_way_sync
            )
            field_kwargs["immutable_type"] = True
            field_kwargs[
                "immutable_properties"
            ] = data_sync_property.immutable_properties
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
