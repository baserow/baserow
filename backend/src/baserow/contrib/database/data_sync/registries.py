from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.data_sync.export_serialized import (
    DataSyncExportSerializedStructure,
)
from baserow.contrib.database.data_sync.models import DataSync, DataSyncSyncedProperty
from baserow.contrib.database.fields.models import Field
from baserow.core.registries import ImportExportConfig
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    ImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.utils import ChildProgressBuilder

User = get_user_model()

ExporterFunc = Callable[[Any, bool], None]


class DataSyncProperty(ABC):
    unique_primary = False
    """
    Indicates whether this property is used to identify a unique row. This will be used
    to identify if a row must be created, updated, or deleted. There must at least be
    one. If multiple are provided, then a unique combination will be used. It's not
    possible for the user to exclude them in the table.
    """

    immutable_properties = False
    """
    Indicates whether the properties of the related field are immutable. This will
    probably be `True` for a date field so that the user can configure how it's
    formatted, but `False` for select options because those should be a fixed set.
    """

    initially_selected = True
    """
    Indicates whether the property must automatically be toggled on before the users
    creates the data sync. This can be used if there are many properties, the user must
    be automatically use them all.
    """

    def __init__(self, key, name, initially_selected=True):
        """
        :param key: A unique key that must never be changed.
        :param name: Human-readable name of the property.
        :param initially_selected: If true, then the property is suggested to be
            enabled.
        """

        self.key = key
        self.name = name
        self.initially_selected = initially_selected

    @abstractmethod
    def to_baserow_field(self) -> Field:
        """
        Should return an unsaved Baserow field instance. This is the field object that
        will be used to automatically create the field.

        :return: An unsaved Baserow field model object.
        """

    def get_metadata(
        self, baserow_field: Field, existing_metadata: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Called after the field is created or updated. It can return metadata that's
        going to be stored in the related DataSyncSyncedProperty. This can for
        example to store a mapping that's needed when the data is synchronized.

        :param baserow_field: The saved/created Baserow field in the synced table.
        :param existing_metadata: Optionally already existing metadata can be provided.
        :return: The mapping that must be stored in the `DataSyncSyncedProperty`.
        """

        return None

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        """
        Checks if the provided cell value is equal. This is used to check if the
        row must be updated.

        :param baserow_row_value: The row value from the Baserow row.
        :param data_sync_row_value:  The row value from the data sync `get_all_rows`
            row.
        :return: `True` if the value is equal.
        """

        return baserow_row_value == data_sync_row_value


class DataSyncType(
    ModelInstanceMixin, CustomFieldsInstanceMixin, ImportExportMixin, Instance, ABC
):
    def prepare_values(self, user: AbstractUser, values: Dict) -> Dict:
        """
        A hook that can validate or changes the provided values.

        :param user: The user on whose behalf the data sync is created or updated.
        :param values: The values that were provided.
        :return: The values that were validated and updates by the data sync type.
        """

        return values

    def prepare_sync_job_values(self, instance: "DataSync"):
        """
        A hook that's called in the `prepare_values` of the job.

        :param instance: The related data sync instance.
        """

    def before_sync_table(self, user: AbstractUser, instance: "DataSync"):
        """
        A hook that's called right before the table sync starts.

        :param user: The user on whose behalf the table is synced.
        :param instance: The related data sync instance.
        """

    @abstractmethod
    def get_properties(self, instance: "DataSync") -> List[DataSyncProperty]:
        """
        Should return a list of property objects that define the schema of the synced
        table. It should list all the available properties, but the user can choose
        which ones they want to add. The `unique_primary` ones are required.

        Properties can be added, changed, or deleted because the fields are synced
        before syncing the row data.

        :param instance: The data sync instance of which the properties must be
            returned.
        :return: List of all properties in the data sync source.
        """

    @abstractmethod
    def get_all_rows(
        self,
        instance: "DataSync",
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Iterable[Dict]:
        """
        Should return a list with dicts containing the raw row values. The values will
        run through the `to_baserow_value` method of the related property to convert
        them to the Baserow format. It must contain all the rows, even if there are
        many. It will be used to figure out:

        - Which rows don't exist, but in this list, and create those.
        - Which rows already exist, update those if changed.
        - Which rows exist, but not in this list, delete those.

        :param instance: The data sync instance of which the rows must be fetched.
        :raises SyncError: If something goes wrong, but don't want to fail hard and
            expose the error via the API.
        :return: Iterable of all rows in the data sync source.
        """

    def export_serialized(self, instance: "DataSync"):
        """
        Exports the data sync properties and the `allowed_fields` to the serialized
        format.
        """

        properties = instance.synced_properties.all()
        type_specific = {
            field: getattr(instance, field) for field in self.allowed_fields
        }
        last_sync_iso = instance.last_sync.isoformat() if instance.last_sync else None
        return DataSyncExportSerializedStructure.data_sync(
            id=instance.id,
            type_name=self.type,
            last_sync=last_sync_iso,
            last_error=instance.last_error,
            properties=[
                DataSyncExportSerializedStructure.property(
                    key=p.key, field_id=p.field_id
                )
                for p in properties
            ],
            **type_specific,
        )

    def import_serialized(
        self,
        table,
        serialized_values,
        id_mapping,
        import_export_config: ImportExportConfig,
    ):
        """
        Imports the data sync properties and the `allowed_fields`.
        """

        if "database_table_data_sync" not in id_mapping:
            id_mapping["database_table_data_sync"] = {}

        serialized_copy = serialized_values.copy()
        original_id = serialized_copy.pop("id")
        properties = serialized_copy.pop("properties", [])
        serialized_copy.pop("type")
        type_properties = {
            field: serialized_copy.get(field) for field in self.allowed_fields
        }
        data_sync = self.model_class.objects.create(
            table=table,
            last_sync=serialized_copy["last_sync"],
            last_error=serialized_copy["last_error"],
            **type_properties,
        )

        properties_to_be_created = []
        for property in properties:
            properties_to_be_created.append(
                DataSyncSyncedProperty(
                    data_sync=data_sync,
                    field_id=id_mapping["database_fields"][property["field_id"]],
                    key=property["key"],
                )
            )

        DataSyncSyncedProperty.objects.bulk_create(properties_to_be_created)

        id_mapping["database_table_data_sync"][original_id] = data_sync.id

        return data_sync


class DataSyncTypeRegistry(ModelRegistryMixin, CustomFieldsRegistryMixin, Registry):
    name = "data_sync"


data_sync_type_registry = DataSyncTypeRegistry()
