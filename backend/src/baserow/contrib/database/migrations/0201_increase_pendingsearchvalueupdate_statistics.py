from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0200_fix_to_timestamptz_formula"),
    ]

    operations = [
        # Increase the statistics value of the field_id so that when `field_id IN (...)`
        # is used on a table with many entries in the
        # `database_pendingsearchvalueupdate`, it will remain performant.
        migrations.RunSQL(
            sql="""
                ALTER TABLE database_pendingsearchvalueupdate
                    ALTER COLUMN field_id SET STATISTICS 500;
            """,
            reverse_sql="""
                ALTER TABLE database_pendingsearchvalueupdate
                    ALTER COLUMN field_id SET STATISTICS 100;
            """
        ),
    ]
