from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin

from .constants import (
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
)


class AIProviderConfig(CreatedAndUpdatedOnMixin, models.Model):
    """An instance-owned AI provider configuration."""

    provider_type = models.CharField(max_length=32, unique=True)
    api_key = models.CharField(max_length=512, blank=True, default="", db_default="")
    extra_settings = models.JSONField(default=dict, blank=True, db_default={})
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.provider_type


class AIProviderModel(models.Model):
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
