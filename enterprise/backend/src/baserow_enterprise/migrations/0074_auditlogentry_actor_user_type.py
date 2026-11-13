from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("baserow_enterprise", "0073_delete_legacy_agent_subjects")]

    operations = [
        migrations.AddField(
            model_name="auditlogentry",
            name="actor_user_type",
            field=models.CharField(max_length=8, null=True),
        ),
    ]
