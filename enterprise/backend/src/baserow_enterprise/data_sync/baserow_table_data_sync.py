from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from baserow_premium.fields.field_types import AIFieldType
from baserow_premium.license.handler import LicenseHandler
from rest_framework import serializers

from baserow.contrib.database.data_sync.data_sync_types import compare_date
from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import DataSyncProperty, DataSyncType
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
    TextFieldType,
    URLFieldType,
    UUIDFieldType,
)
from baserow.contrib.database.fields.models import (
    DateField,
    Field,
    LongTextField,
    NumberField,
    TextField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.utils import ChildProgressBuilder
from baserow_enterprise.features import DATA_SYNC

from .models import LocalBaserowTableDataSync


class RowIDDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class BaserowFieldDataSyncProperty(DataSyncProperty):
    supported_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        EmailFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        BooleanFieldType.type,
        DateFieldType.type,
        DurationFieldType.type,
        FileFieldType.type,
        PhoneNumberFieldType.type,
        CreatedOnFieldType.type,
        LastModifiedFieldType.type,
        UUIDFieldType.type,
        AutonumberFieldType.type,
        AIFieldType.type,
    ]
    field_types_override = {
        CreatedOnFieldType.type: DateField,
        LastModifiedFieldType.type: DateField,
        UUIDFieldType.type: TextField,
        AutonumberFieldType.type: NumberField,
        AIFieldType.type: LongTextField,
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
            }
        )

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
    allowed_fields = ["source_table_id", "authorized_user_id"]
    serializer_field_names = ["source_table_id"]
    serializer_field_overrides = {
        "source_table_id": serializers.IntegerField(
            help_text="The ID of the source table that must be synced.",
            required=True,
            allow_null=False,
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

    def _get_table(self, instance):
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

        return table

    def get_properties(self, instance) -> List[DataSyncProperty]:
        table = self._get_table(instance)
        # The `table_id` is not set if when just listing the properties using the
        # `DataSyncPropertiesView` endpoint, but it will be set when creating the view.
        if instance.table_id:
            LicenseHandler.raise_if_workspace_doesnt_have_feature(
                DATA_SYNC, instance.table.database.workspace
            )
        fields = specific_iterator(table.field_set.all())
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
            in BaserowFieldDataSyncProperty.supported_field_types
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
        table = self._get_table(instance)
        enabled_properties = DataSyncSyncedProperty.objects.filter(data_sync=instance)
        enabled_property_field_ids = [p.key for p in enabled_properties]
        model = table.get_model()
        progress.increment(by=1)  # makes the total `1`
        rows_queryset = model.objects.all().values(*["id"] + enabled_property_field_ids)
        progress.increment(by=9)  # makes the total `10`
        return rows_queryset
