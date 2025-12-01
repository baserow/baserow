from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service


class AIOutputType(models.TextChoices):
    TEXT = "text", "Text"
    CHOICE = "choice", "Choice"


class AIIntegration(Integration):
    # JSONField to store per-provider override settings. Structure:
    # `{"openai": {"api_key": "...", "models": [...]}, ...}`
    ai_settings = models.JSONField(default=dict, blank=True)


class AIAgentService(Service):
    ai_generative_ai_type = models.CharField(
        max_length=32,
        null=True,
        help_text='The generative AI type (e.g. "openai", "anthropic", "mistral")',
    )
    ai_generative_ai_model = models.CharField(
        max_length=128,
        null=True,
        help_text='The specific model name (e.g. "gpt-4", "claude-3-opus")',
    )
    ai_output_type = models.CharField(
        max_length=32,
        choices=AIOutputType.choices,
        default=AIOutputType.TEXT,
    )
    ai_temperature = models.FloatField(null=True)
    ai_prompt = FormulaField(default="")
    ai_choices = models.JSONField(default=list, blank=True)
