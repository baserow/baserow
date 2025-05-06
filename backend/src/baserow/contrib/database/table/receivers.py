from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.models import FileField
from baserow.contrib.database.fields.signals import field_deleted, field_restored
from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_deleted,
    rows_updated,
)
from baserow.contrib.database.table.signals import table_created, table_deleted
from baserow.core.registries import application_type_registry
from baserow.core.signals import application_created

from .tasks import create_tables_usage_for_new_database, update_table_usage


@receiver(rows_created)
def on_rows_created(sender, rows, before, user, table, **kwargs):
    transaction.on_commit(
        lambda: update_table_usage.delay(table.id, row_count=len(rows))
    )


@receiver(rows_deleted)
def on_rows_deleted(sender, rows, user, table, **kwargs):
    transaction.on_commit(
        lambda: update_table_usage.delay(table.id, row_count=-len(rows))
    )


@receiver(rows_updated)
def on_rows_updated(
    sender, rows, user, table, model, before_return, updated_field_ids, **kwargs
):
    # If a file field has been updated, let's recalculate the storage usage at the first
    # opportunity.

    for field_object in model.get_field_objects():
        field = field_object["field"]
        if isinstance(field, FileField) and field.id in updated_field_ids:
            transaction.on_commit(lambda: update_table_usage.delay(table.id))
            break


# Table signals for row count
@receiver(table_created)
def on_table_created(sender, table, user, **kwargs):
    # If rows have been created or imported, they will be counted in the `rows_created`
    # signal, so let's only create an empty placehorder to make sure the table usage
    # will be updated avoiding double counting.
    transaction.on_commit(lambda: update_table_usage.delay(table.id, 0))


@receiver(table_deleted)
def on_table_deleted(sender, table, user, **kwargs):
    row_count = table.get_model().objects.count()
    transaction.on_commit(
        lambda: update_table_usage.delay(table.id, row_count=-row_count)
    )


# Application level signals
@receiver(application_created)
def on_application_created(sender, application, **kwargs):
    application_type = application_type_registry.get_by_model(
        application.specific_class
    )
    if isinstance(application_type, DatabaseApplicationType):
        transaction.on_commit(
            lambda: create_tables_usage_for_new_database.delay(application.id)
        )


# File field signals for storage usage
@receiver([field_restored, field_deleted])
def on_field_restored(sender, field, **kwargs):
    if isinstance(field, FileField):
        transaction.on_commit(lambda: update_table_usage.delay(field.table_id))
