import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0115_populate_ai_providers"),
        ("baserow_premium", "0031_ai_field_scheduled_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="aifield",
            name="ai_provider_model",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The AI provider model to use. When set, takes precedence "
                    "over ai_generative_ai_type and ai_generative_ai_model."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ai_fields",
                to="core.aiprovidermodel",
            ),
        ),
    ]
