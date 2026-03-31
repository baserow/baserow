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
    Table = apps.get_model("database", "Table")

    # Find all unique_primary synced properties whose table has no primary field.
    unique_primary_properties = DataSyncSyncedProperty.objects.filter(
        unique_primary=True
    ).select_related("data_sync", "field")

    for prop in unique_primary_properties:
        table_id = prop.data_sync.table_id
        has_primary = Field.objects.filter(table_id=table_id, primary=True).exists()
        if not has_primary:
            Field.objects.filter(id=prop.field_id).update(primary=True)


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0206_rowhistory_database_ro_action__6ea699_idx"),
    ]

    operations = [
        migrations.RunPython(
            fix_data_sync_missing_primary_field,
            migrations.RunPython.noop,
            elidable=True,
        ),
    ]
