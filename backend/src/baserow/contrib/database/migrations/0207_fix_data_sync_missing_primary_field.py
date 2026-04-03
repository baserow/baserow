from django.db import migrations


def fix_data_sync_missing_primary_field(apps, schema_editor):
    """
    Finds data sync tables that have no primary field and restores primary=True
    on the field associated with their unique_primary synced property.

    This fixes a bug where the primary field could be lost when a user changed
    the primary to a non-unique_primary field, and that field was later removed
    during a data sync.
    """

    DataSyncSyncedProperty = apps.get_model(
        "database", "DataSyncSyncedProperty"
    )
    Field = apps.get_model("database", "Field")

    tables_with_primary = Field.objects.filter(primary=True).values("table_id")
    should_be_primary_field_ids = (
        DataSyncSyncedProperty.objects.filter(unique_primary=True)
        .exclude(data_sync__table_id__in=tables_with_primary)
        .values("field_id")
    )
    Field.objects.filter(id__in=should_be_primary_field_ids).update(primary=True)


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0207_add_view_default_values"),
    ]

    operations = [
        migrations.RunPython(
            fix_data_sync_missing_primary_field,
            migrations.RunPython.noop,
        ),
    ]
