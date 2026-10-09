from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0121_agent"),
        ("integrations", "0037_coreresponseservice_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="localbaserowintegration",
            name="authorized_user",
            field=models.ForeignKey(
                null=True,
                on_delete=models.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_subject_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_subject_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
