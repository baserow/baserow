from django.db import migrations, models

import baserow.core.ai_provider.models


AI_AGENT_FEATURE = "ai_agent"


def add_ai_agent_feature(apps, schema_editor):
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    models_to_update = []
    for model in AIProviderModel.objects.only("id", "feature_types"):
        feature_types = list(model.feature_types or [])
        if AI_AGENT_FEATURE not in feature_types:
            model.feature_types = [*feature_types, AI_AGENT_FEATURE]
            models_to_update.append(model)

    if models_to_update:
        AIProviderModel.objects.bulk_update(models_to_update, ["feature_types"])


def remove_ai_agent_feature(apps, schema_editor):
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    models_to_update = []
    for model in AIProviderModel.objects.only("id", "feature_types"):
        feature_types = list(model.feature_types or [])
        without_ai_agent = [
            feature_type
            for feature_type in feature_types
            if feature_type != AI_AGENT_FEATURE
        ]
        if without_ai_agent != feature_types:
            model.feature_types = without_ai_agent
            models_to_update.append(model)

    if models_to_update:
        AIProviderModel.objects.bulk_update(models_to_update, ["feature_types"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0119_aiproviderfeaturesetting_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiprovidermodel",
            name="feature_types",
            field=models.JSONField(
                blank=True,
                db_default=["ai_fields", "ai_agent"],
                default=(
                    baserow.core.ai_provider.models.get_default_ai_provider_model_feature_types_v2
                ),
                help_text=(
                    "The AI features allowed to select this model. This controls "
                    "eligibility, not which features currently use the model."
                ),
            ),
        ),
        migrations.RunPython(add_ai_agent_feature, remove_ai_agent_feature),
    ]
