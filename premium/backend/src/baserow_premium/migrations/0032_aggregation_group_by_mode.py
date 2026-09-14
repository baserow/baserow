from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("baserow_premium", "0031_ai_field_scheduled_update")]

    operations = [
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
