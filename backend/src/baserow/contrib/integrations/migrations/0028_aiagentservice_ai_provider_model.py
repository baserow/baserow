import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0115_populate_ai_providers"),
        ("integrations", "0027_coresmtpemailservice_use_instance_smtp_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiagentservice",
            name="ai_provider_model",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The AI provider model to use. When set, takes precedence "
                    "over ai_generative_ai_type and ai_generative_ai_model."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ai_agent_services",
                to="core.aiprovidermodel",
            ),
        ),
    ]
