from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("baserow_enterprise", "0070_semantic_search")]

    operations = [
        migrations.AddField(
            model_name="auditlogentry",
            name="actor_identity_type",
            field=models.CharField(max_length=16, null=True),
        ),
    ]
