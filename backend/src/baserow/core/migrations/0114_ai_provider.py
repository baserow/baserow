import baserow.core.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0113_alter_notification_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIProviderConfig",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", baserow.core.fields.SyncedDateTimeField(auto_now=True)),
                (
                    "provider_type",
                    models.CharField(
                        help_text=(
                            "Registry key identifying the provider type, "
                            'e.g. "openai", "anthropic", "ollama".'
                        ),
                        max_length=32,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text=(
                            "Human-readable label, "
                            'e.g. "OpenAI Premium", "Ollama Local".'
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "api_key",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "API key for the provider. "
                            "Stored as plain text for now."
                        ),
                        max_length=512,
                    ),
                ),
                (
                    "extra_settings",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Provider-specific settings: organization, base_url, host, etc. Structure varies per provider_type.",
                    ),
                ),
                (
                    "scope_object_id",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            "The ID of the scope object. "
                            "NULL means instance-level."
                        ),
                        null=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Whether this provider is active "
                            "and available for use."
                        ),
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_ai_providers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "scope_content_type",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The content type of the scope object. "
                            "NULL means instance-level."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="aiproviderconfig",
            index=models.Index(
                fields=["scope_content_type", "scope_object_id"],
                name="ai_provider_scope_idx",
            ),
        ),
        migrations.CreateModel(
            name="AIProviderModel",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "model_identifier",
                    models.CharField(
                        help_text=(
                            "The model identifier, "
                            'e.g. "gpt-4o", "claude-sonnet-4-20250514".'
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Optional human-friendly display name for the model."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Whether this model is enabled "
                            "and available for use."
                        ),
                    ),
                ),
                (
                    "last_test_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the last test call was made.",
                        null=True,
                    ),
                ),
                (
                    "last_test_status",
                    models.CharField(
                        blank=True,
                        help_text=(
                            'Result of the last test: "success", '
                            '"failure", or NULL (never tested).'
                        ),
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    "last_test_error",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text=(
                            "Error message if the last test failed."
                        ),
                    ),
                ),
                (
                    "provider_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="models",
                        to="core.aiproviderconfig",
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Sort order within the provider.",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="AIProviderModelFeature",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "feature_type",
                    models.CharField(
                        help_text=(
                            "Registry key for the feature, "
                            'e.g. "ai_field", "ai_assistant".'
                        ),
                        max_length=64,
                    ),
                ),
                (
                    "provider_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="features",
                        to="core.aiprovidermodel",
                    ),
                ),
            ],
            options={
                "unique_together": {("provider_model", "feature_type")},
            },
        ),
        migrations.CreateModel(
            name="AIProviderOverride",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "scope_object_id",
                    models.PositiveIntegerField(
                        help_text=(
                            "The ID of the scope object "
                            "doing the overriding."
                        ),
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Whether the inherited provider "
                            "is enabled at this scope."
                        ),
                    ),
                ),
                (
                    "provider_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overrides",
                        to="core.aiproviderconfig",
                    ),
                ),
                (
                    "scope_content_type",
                    models.ForeignKey(
                        help_text=(
                            "The content type of the scope "
                            "doing the overriding."
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    (
                        "provider_config",
                        "scope_content_type",
                        "scope_object_id",
                    )
                },
            },
        ),
        migrations.CreateModel(
            name="AIFeatureDefaultModel",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "feature_type",
                    models.CharField(
                        help_text=(
                            "Registry key for the feature, "
                            'e.g. "ai_assistant".'
                        ),
                        max_length=64,
                    ),
                ),
                (
                    "scope_object_id",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            "The ID of the scope object. "
                            "NULL means instance-level default."
                        ),
                        null=True,
                    ),
                ),
                (
                    "provider_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feature_defaults",
                        to="core.aiprovidermodel",
                    ),
                ),
                (
                    "scope_content_type",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The content type of the scope. "
                            "NULL means instance-level default."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    (
                        "feature_type",
                        "scope_content_type",
                        "scope_object_id",
                    )
                },
            },
        ),
    ]
