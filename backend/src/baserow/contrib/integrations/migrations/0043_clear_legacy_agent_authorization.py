from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0042_corehttpdatasourceservice"),
    ]

    operations = [
        # An unauthorized integration reports a clear error; an Agent one would crash.
        migrations.RunSQL(
            "UPDATE integrations_localbaserowintegration "
            "SET authorized_subject_type = NULL, authorized_user_id = NULL "
            "WHERE authorized_subject_type = 'core.Agent'",
            migrations.RunSQL.noop,
        ),
    ]
