from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin

from .constants import (
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
)


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
    last_test_at = models.DateTimeField(null=True, blank=True, db_default=None)
    last_test_status = models.CharField(
        max_length=16,
        choices=TestStatus.choices,
        null=True,
        blank=True,
        db_default=None,
    )
    last_test_error = models.TextField(blank=True, default="", db_default="")

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
