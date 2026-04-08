from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "baserow_enterprise",
            "0059_datascanresultexportjob_datascan_datascanlistitem_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="datascan",
            name="whole_words",
            field=models.BooleanField(db_default=True, default=True),
        ),
    ]
