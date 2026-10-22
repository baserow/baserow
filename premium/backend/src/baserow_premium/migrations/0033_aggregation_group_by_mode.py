from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_premium", "0032_aifield_long_text_enable_rich_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="chartseriesconfig",
            name="series_color",
            field=models.CharField(max_length=9, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="piechartseriesconfig",
            name="series_color",
            field=models.CharField(max_length=9, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="localbaserowgroupedaggregaterows",
            name="bucket_limit",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                help_text="Maximum result buckets, including Other. Null uses the server maximum.",
            ),
        ),
        migrations.AddField(
            model_name="localbaserowtableserviceaggregationgroupby",
            name="mode",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("complete", "Complete selection"),
                    ("individual", "Each selected option"),
                ],
                default="complete",
                db_default="complete",
                help_text="Whether to group multiple selections together or by each option.",
            ),
        ),
    ]
