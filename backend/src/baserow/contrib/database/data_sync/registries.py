from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from celery.app.task import Context

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
    two_way_sync_strategy_type = None
    """
    By default, a data sync type is one way, allowing data to be pulled into Baserow.
    This property indicates which two-way sync strategy could be used. There can be a
    difference between strategy depending on the data source. If none, then only a
    one-way data sync is possible.
    """

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
        :param progress_builder: Optionally indicate the progress.
        :raises SyncError: If something goes wrong, but don't want to fail hard and
            expose the error via the API.
        :return: Iterable of all rows in the data sync source.
        """

    def create_rows(
        self, serialized_rows: List[dict], data_sync: "DataSync"
    ) -> (List)[dict]:
        """
        If a `two_way_sync_strategy_type` is set, and `data_sync.two_way_sync` is True,
        then this method is called when a rows are created is the data sync table. Its
        purpose is to make the needed change in the data sync source immediately.

        :param serialized_rows: List containing the serialized rows that were created.
        :param data_sync: The data sync object of the table where the rows were created.
        :return: A list of row dicts that must be updated. This is typically used to
            set the newly created unique primary.
        """

        raise NotImplementedError(
            "A two-way data sync must implement the `create_rows` method."
        )

    def update_rows(
        self,
        serialized_rows: List[dict],
        data_sync: "DataSync",
        updated_field_ids: List[int],
    ):
        """
        If a `two_way_sync_strategy_type` is set, and `data_sync.two_way_sync` is True,
        then this method is called when a rows are updated is the data sync table. Its
        purpose is to make the needed change in the data sync source immediately.

        :param serialized_rows: List containing the serialized rows that were updated.
        :param data_sync: The data sync object of the table where the rows were updated.
        :param updated_field_ids: Contains the field ids that actually changed.
        """

        raise NotImplementedError(
            "A two-way data sync must implement the `update_rows` method."
        )

    def delete_rows(self, serialized_rows: List[dict], data_sync: "DataSync"):
        """
        If a `two_way_sync_strategy_type` is set, and `data_sync.two_way_sync` is True,
        then this method is called when a rows are updated is the data sync table. Its
        purpose is to make the needed change in the data sync source immediately.

        :param serialized_rows: List containing the serialized rows that were updated.
        :param data_sync: The data sync object of the table where the rows were updated.
        :param updated_field_ids: Contains the field ids that actually changed.
        """

        raise NotImplementedError(
            "A two-way data sync must implement the `delete_rows` method."
        )

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


class TwoWaySyncStrategy(Instance, ABC):
    """
    The two-way sync strategy sits in between a celery task that's called when rows are
    created, updated, or deleted in the data sync table, and the update in the source
    data. It's not supposed to update the source data, but it does determine how and
    when the data is updated. It could for make changes in real-time or queue them up.
    """

    def before_enable(self):
        """
        Hook that is called before a two-way sync is created or updated, and the two-way
        sync is enabled.
        """

    def rows_created(
        self, task_context: Context, serialized_rows: List[dict], data_sync: DataSync
    ):
        """
        Called when rows are created in the data sync table. These are by default
        routed through a celery task.

        :param task_context: The context object of the task. Can be used for retrying.
        :param serialized_rows: List containing the serialized rows that were created.
        :param data_sync: The data sync object of the table where the rows were created.
        """

        raise NotImplementedError(
            "Two-way sync strategy must implement the `rows_created` method."
        )

    def rows_updated(
        self,
        task_context: Context,
        serialized_rows: List[dict],
        data_sync: DataSync,
        updated_field_ids: List[int],
    ):
        """
        Called when rows are updated in the data sync table. These are by default
        routed through a celery task.

        :param task_context: The context object of the task. Can be used for retrying.
        :param serialized_rows: List containing the serialized rows that were updated.
        :param data_sync: The data sync object of the table where the rows were updated.
        :param updated_field_ids: Contains the field ids that actually changed.
        """

        raise NotImplementedError(
            "Two-way sync strategy must implement the `rows_updated` method."
        )

    def rows_deleted(self, serialized_rows: List[dict], data_sync: DataSync):
        """
        Called when rows are deleted in the data sync table. These are by default
        routed through a celery task.

        :param task_context: The context object of the task. Can be used for retrying.
        :param serialized_rows: List containing the serialized rows that were deleted.
        :param data_sync: The data sync object of the table where the rows were deleted.
        """

        raise NotImplementedError(
            "Two-way sync strategy must implement the `rows_deleted` method."
        )


class TwoWaySyncStrategyTypeRegistry(Registry):
    name = "two_way_sync_strategy"


data_sync_type_registry = DataSyncTypeRegistry()
two_way_sync_strategy_type_registry = TwoWaySyncStrategyTypeRegistry()
