from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
)


class DataSync(
    CreatedAndUpdatedOnMixin,
    PolymorphicContentTypeMixin,
    models.Model,
    WithRegistry,
):
    table = models.OneToOneField(
        "database.Table",
        on_delete=models.CASCADE,
        related_name="data_sync",
        help_text="The table where the data is synced into.",
    )
    last_sync = models.DateTimeField(
        null=True, help_text="Timestamp when the table was last synced."
    )
    last_error = models.TextField(
        null=True,
        help_text="",
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="data_syncs",
        on_delete=models.CASCADE,
    )
    properties = models.ManyToManyField(Field, through="DataSyncSyncedProperty")
    auto_add_new_properties = models.BooleanField(
        default=False,
        db_default=False,
        help_text="If enabled and new properties are detected on sync, then they're "
        "automatically added. Note that this means all properties will always be added.",
    )
    two_way_sync = models.BooleanField(
        default=False,
        db_default=False,
        help_text="If enabled, then it's possible to make changes to the synced "
        "table. They will automatically be synced with the source data. Note that "
        "this is only possible if the data sync type has a two-way sync strategy.",
    )
    two_way_sync_consecutive_failures = models.PositiveSmallIntegerField(
        default=0,
        db_default=0,
        help_text="Indicates the total number of two-way sync consecutive failures. Can"
        "be used by the strategy to disable the two-way sync if needed.",
    )

    @staticmethod
    def get_type_registry():
        """Returns the registry related to this model class."""

        from baserow.contrib.database.data_sync.registries import (
            data_sync_type_registry,
        )

        return data_sync_type_registry


class DataSyncSyncedProperty(models.Model):
    """
    An entry represents the visible property of the data sync table. If the entry
    doesn't exist, then the property is not visible as field in the table.
    """

    data_sync = models.ForeignKey(
        DataSync, on_delete=models.CASCADE, related_name="synced_properties"
    )
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    key = models.CharField(
        max_length=255, help_text="The matching `key` of the `DataSyncProperty`."
    )
    # This field must be stored in this model because it must be exposed via the API,
    # and we can't call the `get_properties` method everytime it's needed because it
    # could be slow.
    unique_primary = models.BooleanField(
        default=False,
        help_text="Indicates whether the data sync property is used for unique "
        "identification when syncing.",
    )
    metadata = models.JSONField(
        null=True,
        default=None,
        help_text="Private metadata needed to help keep the data in sync.",
    )


class SyncDataSyncTableJob(Job):
    data_sync = models.ForeignKey(
        DataSync,
        null=True,
        related_name="sync_data_sync_table_job",
        on_delete=models.SET_NULL,
        help_text="The data sync of which the table must be synced.",
    )


class ICalCalendarDataSync(DataSync):
    ical_url = models.URLField(max_length=2000)


class PostgreSQLDataSync(DataSync):
    postgresql_host = models.CharField(max_length=255)
    postgresql_username = models.CharField(max_length=255)
    postgresql_password = models.CharField(max_length=255)
    postgresql_port = models.PositiveSmallIntegerField(default=5432)
    postgresql_database = models.CharField(max_length=255)
    postgresql_schema = models.CharField(max_length=255, default="public")
    postgresql_table = models.CharField(max_length=255)
    postgresql_sslmode = models.CharField(
        max_length=12,
        default="prefer",
        choices=(
            ("disable", "disable"),
            ("allow", "allow"),
            ("prefer", "prefer"),
            ("require", "require"),
            ("verify-ca", "verify-ca"),
            ("verify-full", "verify-full"),
        ),
    )
