from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.db.models import Prefetch

from baserow_premium.fields.field_types import AIFieldType
from baserow_premium.fields.registries import ai_field_output_registry
from baserow_premium.license.handler import LicenseHandler
from rest_framework import serializers

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import DataSyncProperty, DataSyncType
from baserow.contrib.database.data_sync.utils import (
    compare_date,
    update_baserow_field_select_options,
)
from baserow.contrib.database.fields.field_types import (
    AutonumberFieldType,
    BooleanFieldType,
    CreatedOnFieldType,
    DateFieldType,
    DurationFieldType,
    EmailFieldType,
    FileFieldType,
    LastModifiedFieldType,
    LongTextFieldType,
    NumberFieldType,
    PhoneNumberFieldType,
    RatingFieldType,
    SingleSelectFieldType,
    TextFieldType,
    URLFieldType,
    UUIDFieldType,
)
from baserow.contrib.database.fields.models import (
    DateField,
    Field,
    NumberField,
    TextField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.db import specific_iterator, specific_queryset
from baserow.core.handler import CoreHandler
from baserow.core.utils import ChildProgressBuilder
from baserow_enterprise.features import DATA_SYNC

from .models import LocalBaserowTableDataSync


def prepare_single_select_value(value, field, metadata):
    try:
        # The metadata contains a mapping of the select options where the key is the
        # old ID and the value is the new ID. For some reason the key is converted to
        # a string when moved into the JSON field.
        return metadata["select_options_mapping"][str(value)]
    except (KeyError, TypeError):
        return None


def prepare_ai_value(value, field, metadata):
    output_type = ai_field_output_registry.get(field.ai_output_type)
    return output_type.prepare_data_sync_value(value, field, metadata)


# List of Baserow supported field types that can be included in the data sync.
supported_field_types = {
    TextFieldType.type: {},
    LongTextFieldType.type: {},
    URLFieldType.type: {},
    EmailFieldType.type: {},
    NumberFieldType.type: {},
    RatingFieldType.type: {},
    BooleanFieldType.type: {},
    DateFieldType.type: {},
    DurationFieldType.type: {},
    FileFieldType.type: {},
    PhoneNumberFieldType.type: {},
    CreatedOnFieldType.type: {},
    LastModifiedFieldType.type: {},
    UUIDFieldType.type: {},
    AutonumberFieldType.type: {},
    AIFieldType.type: {"prepare_value": prepare_ai_value},
    SingleSelectFieldType.type: {"prepare_value": prepare_single_select_value},
}


class RowIDDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class BaserowFieldDataSyncProperty(DataSyncProperty):
    field_types_override = {
        CreatedOnFieldType.type: DateField,
        LastModifiedFieldType.type: DateField,
        UUIDFieldType.type: TextField,
        AutonumberFieldType.type: NumberField,
    }

    def __init__(self, field, immutable_properties, **kwargs):
        self.field = field
        self.immutable_properties = immutable_properties
        super().__init__(**kwargs)

    def to_baserow_field(self) -> Field:
        field_type = field_type_registry.get_by_model(self.field)
        allowed_fields = ["name"] + field_type.allowed_fields
        model_class = self.field_types_override.get(
            field_type.type, field_type.model_class
        )
        return model_class(
            **{
                allowed_field: getattr(self.field, allowed_field)
                for allowed_field in allowed_fields
                if hasattr(self.field, allowed_field)
                and hasattr(model_class, allowed_field)
                # Select options can't be set directly because that results in an error.
                and allowed_field != "select_options"
            }
        )

    def get_metadata(self, baserow_field, existing_metadata=None):
        new_metadata = super().get_metadata(baserow_field, existing_metadata)
        field_type = field_type_registry.get_by_model(baserow_field)

        # If the field type doesn't support select options, then there is no reason
        # fetch them, create new ones, and return the mapping.
        if not field_type.can_have_select_options:
            return new_metadata

        if new_metadata is None:
            new_metadata = {}

        # Based on the existing mapping, we can figure out which select options must
        # be created, updated, and deleted in the synced field.
        existing_mapping = {}
        if existing_metadata:
            existing_mapping = existing_metadata.get("select_options_mapping", {})

        select_options_mapping = update_baserow_field_select_options(
            self.field.select_options.all(),
            baserow_field,
            existing_mapping,
        )
        new_metadata["select_options_mapping"] = select_options_mapping

        return new_metadata

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        # The CreatedOn and LastModified fields are always stored as datetime in the
        # source table, but not always in the data sync table, so if that happens we'll
        # compare loosely.
        if isinstance(baserow_row_value, date) and isinstance(
            data_sync_row_value, datetime
        ):
            return compare_date(baserow_row_value, data_sync_row_value)
        # The baserow row value is converted to a string, so we would need to convert
        # the uuid object to a string to do a good comparison.
        if isinstance(data_sync_row_value, UUID):
            data_sync_row_value = str(data_sync_row_value)
        return super().is_equal(baserow_row_value, data_sync_row_value)


class LocalBaserowTableDataSyncType(DataSyncType):
    type = "local_baserow_table"
    model_class = LocalBaserowTableDataSync
    allowed_fields = ["source_table_id", "source_table_view_id", "authorized_user_id"]
    serializer_field_names = ["source_table_id", "source_table_view_id"]
    serializer_field_overrides = {
        "source_table_id": serializers.IntegerField(
            help_text="The ID of the source table that must be synced.",
            required=True,
            allow_null=False,
        ),
        "source_table_view_id": serializers.IntegerField(
            help_text="If provided, then only the visible fields and rows matching the "
            "filters will be synced.",
            required=False,
            allow_null=True,
        ),
    }

    def prepare_values(self, user, values):
        # The user that creates the data sync is automatically the one on whose
        # behalf the data is synced in the future.
        values["authorized_user_id"] = user.id
        return values

    def prepare_sync_job_values(self, instance):
        # Raise the error so that the job doesn't start and the user is informed with
        # the correct error.
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, instance.table.database.workspace
        )

    def before_sync_table(self, user, instance):
        # If the authorized user was deleted, or the table was duplicated,
        # the authorized user is set to `None`. In this case, we're setting the
        # authorized user to the user on whos behalf the table is synced so that it
        # will work.
        if instance.authorized_user is None:
            instance.authorized_user = user
            instance.save()

    def _get_table_and_view(self, instance):
        try:
            table = TableHandler().get_table(instance.source_table_id)
        except TableDoesNotExist:
            raise SyncError("The source table doesn't exist.")

        if not CoreHandler().check_permissions(
            instance.authorized_user,
            ReadDatabaseRowOperationType.type,
            workspace=table.database.workspace,
            context=table,
            raise_permission_exceptions=False,
        ):
            raise SyncError("The authorized user doesn't have access to the table.")

        view = None
        view_id = instance.source_table_view_id
        if view_id is not None:
            try:
                view = (
                    ViewHandler()
                    .get_view_as_user(
                        instance.authorized_user,
                        instance.source_table_view_id,
                        table_id=table.id,
                    )
                    .specific
                )
            except ViewDoesNotExist:
                raise SyncError(f"The view with id {view_id} does not exist.")

        return table, view

    def get_properties(self, instance) -> List[DataSyncProperty]:
        table, view = self._get_table_and_view(instance)
        # The `table_id` is not set if when just listing the properties using the
        # `DataSyncTypePropertiesView` endpoint, but it will be set when creating the
        # view.
        if instance.table_id:
            LicenseHandler.raise_if_workspace_doesnt_have_feature(
                DATA_SYNC, instance.table.database.workspace
            )

        field_queryset = table.field_set.all().prefetch_related("select_options")

        # If a view is provided, then we don't want to expose hidden fields,
        # so we filter on the visible options to prevent that.
        if view:
            view_type = view_type_registry.get_by_model(view)
            visible_field_options = view_type.get_visible_field_options_in_order(view)
            visible_field_ids = {o.field_id for o in visible_field_options}
            field_queryset = field_queryset.filter(id__in=visible_field_ids)

        fields = specific_iterator(field_queryset)
        properties = [RowIDDataSyncProperty("id", "Row ID")]

        return properties + [
            BaserowFieldDataSyncProperty(
                field=field,
                immutable_properties=True,
                key=f"field_{field.id}",
                name=field.name,
            )
            for field in fields
            if field_type_registry.get_by_model(field).type
            in supported_field_types.keys()
        ]

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        # The progress bar is difficult to setup because there are only two steps
        # that must completed. We're therefore using working with a total of 10 where
        # most of it is related to fetching the row values.
        progress = ChildProgressBuilder.build(progress_builder, child_total=10)
        table, view = self._get_table_and_view(instance)
        enabled_properties = DataSyncSyncedProperty.objects.filter(
            data_sync=instance
        ).prefetch_related(
            Prefetch("field", queryset=specific_queryset(Field.objects_and_trash.all()))
        )
        enabled_property_field_ids = [p.key for p in enabled_properties]
        model = table.get_model()
        queryset = model.objects.all()

        # If a view is provided then we must not expose rows that don't match the
        # filters.
        if view:
            queryset = ViewHandler().apply_filters(view, queryset)
            queryset = ViewHandler().apply_sorting(view, queryset)

        progress.increment(by=1)  # makes the total `1`
        rows_queryset = queryset.values(*["id"] + enabled_property_field_ids)
        progress.increment(by=7)  # makes the total `8`

        # Loop over all properties and rows to prepare the value if needed .This is
        # used to map the select options cell value, for example.
        for enabled_property in enabled_properties:
            # No need to change the value for the ID because that field not
            # dynamically part of the source table schema.
            if enabled_property.key == "id":
                continue

            # Even though `enabled_property.field` is the synced field and not the
            # source field, we can safely use that to get the supported field object
            # because the target and source field is equal.
            field_type = field_type_registry.get_by_model(
                enabled_property.field.specific_class
            )
            supported_field = supported_field_types[field_type.type]
            if "prepare_value" in supported_field:
                for row in rows_queryset:
                    row[enabled_property.key] = supported_field["prepare_value"](
                        row[enabled_property.key],
                        enabled_property.field,
                        enabled_property.metadata,
                    )
        progress.increment(by=2)  # makes the total `10`

        return rows_queryset

    def import_serialized(
        self, table, serialized_values, id_mapping, import_export_config
    ):
        serialized_copy = serialized_values.copy()
        # Always unset the authorized user for security reasons. This is okay because
        # the first user to sync the data sync table will become the authorized user.
        serialized_copy["authorized_user_id"] = None
        source_table_id = serialized_copy["source_table_id"]

        if source_table_id in id_mapping["database_tables"]:
            # If the source table exists in the mapping, it means that it was
            # included in the export. In that case, we want to use that one as source
            # table instead of the existing one.
            serialized_copy["source_table_id"] = id_mapping["database_tables"][
                source_table_id
            ]
            serialized_copy["authorized_user_id"] = None
            data_sync = super().import_serialized(
                table, serialized_copy, id_mapping, import_export_config
            )

            # Because we're now pointing to the newly imported data sync source table,
            # the field id keys must also be remapped.
            properties_to_update = []
            for data_sync_property in data_sync.synced_properties.all():
                key_field_id = get_field_id_from_field_key(data_sync_property.key)
                if key_field_id:
                    new_field_id = id_mapping["database_fields"][key_field_id]
                    data_sync_property.key = f"field_{new_field_id}"
                    properties_to_update.append(data_sync_property)
            DataSyncSyncedProperty.objects.bulk_update(properties_to_update, ["key"])

            return data_sync

        if import_export_config.is_duplicate:
            # When duplicating the database or table, and it doesn't exist in the
            # id_mapping, then the source table is inside the same database or in
            # another workspace. In that case, we want to keep using the same.
            return super().import_serialized(
                table, serialized_copy, id_mapping, import_export_config
            )

        # If the source table doesn't exist in the mapping, and we're not
        # duplicating, then it's not possible to preserve the data sync. We'll then
        # transform the fields to editable fields, keep the data, and keep the table
        # as regular table.
        table.field_set.all().update(
            read_only=False, immutable_type=False, immutable_properties=False
        )
        return None
