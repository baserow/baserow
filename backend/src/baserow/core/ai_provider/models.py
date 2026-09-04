from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin

from .constants import (
    AI_PROVIDER_FEATURE_AI_AGENT,
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
)


def get_default_ai_provider_model_feature_types() -> list[str]:
    """Return the historical default referenced by migration 0119."""

    return [AI_PROVIDER_FEATURE_AI_FIELDS]


def get_default_ai_provider_model_feature_types_v2() -> list[str]:
    """Keep current ORM callers compatible with every legacy model consumer."""

    return [AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_AI_AGENT]


class AIProviderConfig(CreatedAndUpdatedOnMixin, models.Model):
    """An instance- or workspace-owned AI provider configuration."""

    workspace = models.ForeignKey(
        "core.Workspace",
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.CASCADE,
        related_name="ai_provider_configs",
    )
    provider_type = models.CharField(max_length=32)
    api_key = models.CharField(max_length=512, blank=True, default="", db_default="")
    extra_settings = models.JSONField(default=dict, blank=True, db_default={})
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("provider_type",),
                condition=models.Q(workspace__isnull=True),
                name="unique_instance_ai_provider_type",
            ),
            models.UniqueConstraint(
                fields=("workspace", "provider_type"),
                condition=models.Q(workspace__isnull=False),
                name="unique_workspace_ai_provider_type",
            ),
        ]

    def __str__(self):
        return self.provider_type


class AIProviderModel(models.Model):
    """An AI model exposed by an AI provider."""

    class TestStatus(models.TextChoices):
        SUCCESS = AI_PROVIDER_TEST_STATUS_SUCCESS, "Success"
        FAILURE = AI_PROVIDER_TEST_STATUS_FAILURE, "Failure"

    provider_config = models.ForeignKey(
        AIProviderConfig,
        on_delete=models.CASCADE,
        related_name="models",
    )
    model_identifier = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=True, db_default=True)
    feature_types = models.JSONField(
        default=get_default_ai_provider_model_feature_types_v2,
        blank=True,
        db_default=[AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_AI_AGENT],
        help_text=(
            "The AI features allowed to select this model. This controls "
            "eligibility, not which features currently use the model."
        ),
    )
    last_test_at = models.DateTimeField(null=True, blank=True, db_default=None)
    last_test_status = models.CharField(
        max_length=16,
        choices=TestStatus.choices,
        null=True,
        blank=True,
        db_default=None,
    )
    last_test_error = models.TextField(blank=True, default="", db_default="")
    last_test_capabilities = models.JSONField(
        blank=True,
        default=dict,
        db_default={},
        help_text=(
            "The reusable capability results from the last model test. Feature "
            "results are derived from these values."
        ),
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("provider_config", "model_identifier"),
                name="unique_ai_provider_model_identifier",
            )
        ]

    def __str__(self):
        return self.model_identifier


class AIProviderFeatureSetting(models.Model):
    """A scoped default-model choice for one AI feature."""

    workspace = models.ForeignKey(
        "core.Workspace",
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.CASCADE,
        related_name="ai_provider_feature_settings",
        help_text=(
            "The workspace this selection applies to. Null means instance-wide; "
            "the absence of a workspace setting means inherit the instance selection."
        ),
    )
    feature_type = models.CharField(
        max_length=64,
        db_default="",
        help_text=(
            "The AI feature whose scoped default-model selection this setting controls."
        ),
    )
    model = models.ForeignKey(
        AIProviderModel,
        null=True,
        blank=True,
        db_default=None,
        on_delete=models.RESTRICT,
        related_name="feature_settings",
        help_text=(
            "The model actually selected for this feature at this scope. The model "
            "must also list the feature in its feature availability."
        ),
    )
    is_enabled = models.BooleanField(
        default=True,
        db_default=True,
        help_text=(
            "Whether this feature uses the selected model at this scope. False "
            "represents an explicit disable and requires the model to be null."
        ),
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_enabled=False, model__isnull=True)
                    | models.Q(is_enabled=True, model__isnull=False)
                ),
                name="valid_ai_provider_feature_setting_model",
            ),
            models.UniqueConstraint(
                fields=("feature_type",),
                condition=models.Q(workspace__isnull=True),
                name="unique_instance_ai_provider_feature_setting",
            ),
            models.UniqueConstraint(
                fields=("workspace", "feature_type"),
                condition=models.Q(workspace__isnull=False),
                name="unique_workspace_ai_provider_feature_setting",
            ),
        ]

    def __str__(self):
        return self.feature_type


class AIProviderWorkspaceOverride(models.Model):
    """Disables an inherited instance AI provider for one workspace."""

    workspace = models.ForeignKey(
        "core.Workspace",
        on_delete=models.CASCADE,
        related_name="ai_provider_overrides",
    )
    provider_config = models.ForeignKey(
        AIProviderConfig,
        on_delete=models.CASCADE,
        related_name="workspace_overrides",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "provider_config"),
                name="unique_workspace_ai_provider_override",
            )
        ]
