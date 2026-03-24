from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin


class AIProviderConfig(CreatedAndUpdatedOnMixin, models.Model):
    """
    A configured AI provider at a given scope level.

    Scope is determined by the GenericForeignKey:
    - scope_content_type=NULL, scope_object_id=NULL → instance-level (admin-managed)
    - scope_content_type=Workspace CT → workspace-level
    - scope_content_type=Application CT → application-level
    """

    provider_type = models.CharField(
        max_length=32,
        help_text=(
            "Registry key identifying the provider type, "
            'e.g. "openai", "anthropic", "ollama".'
        ),
    )
    name = models.CharField(
        max_length=255,
        help_text='Human-readable label, e.g. "OpenAI Premium", "Ollama Local".',
    )
    api_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="API key for the provider. Stored as plain text for now.",
    )
    extra_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Provider-specific settings: organization, base_url, host, etc. "
            "Structure varies per provider_type."
        ),
    )
    scope_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The content type of the scope object. NULL means instance-level.",
    )
    scope_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="The ID of the scope object. NULL means instance-level.",
    )
    scope = GenericForeignKey("scope_content_type", "scope_object_id")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ai_providers",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this provider is active and available for use.",
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["scope_content_type", "scope_object_id"],
                name="ai_provider_scope_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.provider_type})"

    @property
    def is_instance_level(self):
        return self.scope_content_type_id is None and self.scope_object_id is None


class AIProviderModel(models.Model):
    """
    A specific model offered by an AI provider configuration.
    E.g. "gpt-4o", "claude-sonnet-4-20250514".
    """

    provider_config = models.ForeignKey(
        AIProviderConfig,
        on_delete=models.CASCADE,
        related_name="models",
    )
    model_identifier = models.CharField(
        max_length=255,
        help_text='The model identifier, e.g. "gpt-4o", "claude-sonnet-4-20250514".',
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional human-friendly display name for the model.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this model is enabled and available for use.",
    )
    last_test_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last test call was made.",
    )
    last_test_status = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        help_text='Result of the last test: "success", "failure", or NULL (never tested).',
    )
    last_test_error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if the last test failed.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order within the provider.",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        name = self.display_name or self.model_identifier
        return f"{name} ({self.provider_config.name})"


class AIProviderModelFeature(models.Model):
    """
    Links an AI provider model to a feature it supports.
    E.g. model "gpt-4o" supports features "ai_field" and "ai_assistant".
    """

    provider_model = models.ForeignKey(
        AIProviderModel,
        on_delete=models.CASCADE,
        related_name="features",
    )
    feature_type = models.CharField(
        max_length=64,
        help_text='Registry key for the feature, e.g. "ai_field", "ai_assistant".',
    )

    class Meta:
        unique_together = ("provider_model", "feature_type")

    def __str__(self):
        return f"{self.provider_model} → {self.feature_type}"


class AIProviderOverride(models.Model):
    """
    Allows a child scope to toggle an inherited provider on/off.
    E.g. a workspace can disable an instance-level provider for itself.
    """

    provider_config = models.ForeignKey(
        AIProviderConfig,
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    scope_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The content type of the scope doing the overriding.",
    )
    scope_object_id = models.PositiveIntegerField(
        help_text="The ID of the scope object doing the overriding.",
    )
    scope = GenericForeignKey("scope_content_type", "scope_object_id")
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether the inherited provider is enabled at this scope.",
    )

    class Meta:
        unique_together = ("provider_config", "scope_content_type", "scope_object_id")

    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"Override {self.provider_config} → {status}"


class AIFeatureDefaultModel(models.Model):
    """
    Per-scope default model for a feature that needs one.
    E.g. "ai_assistant" defaults to model X at instance scope,
    but workspace Y overrides it with model Z.

    Resolution: application default → workspace default → instance default.
    """

    feature_type = models.CharField(
        max_length=64,
        help_text='Registry key for the feature, e.g. "ai_assistant".',
    )
    provider_model = models.ForeignKey(
        AIProviderModel,
        on_delete=models.CASCADE,
        related_name="feature_defaults",
    )
    scope_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The content type of the scope. NULL means instance-level default.",
    )
    scope_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="The ID of the scope object. NULL means instance-level default.",
    )
    scope = GenericForeignKey("scope_content_type", "scope_object_id")

    class Meta:
        unique_together = ("feature_type", "scope_content_type", "scope_object_id")

    def __str__(self):
        return f"Default for {self.feature_type}: {self.provider_model}"
