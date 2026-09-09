from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0121_agent"),
        ("integrations", "0037_coreresponseservice_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_agent",
            field=models.ForeignKey(
                blank=True,
                db_default=None,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.agent",
            ),
        ),
    ]
