from io import StringIO

from django.core.management import call_command

import pytest

from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
from baserow.core.ai_provider.models import AIProviderConfig


def _clear_provider_environment(settings):
    for config in PROVIDER_ENVIRONMENT_SETTINGS.values():
        if config["api_key"]:
            setattr(settings, config["api_key"], "")
        setattr(settings, config["models"], [])
        for setting_name in config["extra_settings"].values():
            setattr(settings, setting_name, "")


@pytest.mark.django_db
def test_command_previews_then_imports_without_printing_secrets(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OPENAI_API_KEY = "super-secret"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]
    settings.BASEROW_OPENAI_ORGANIZATION = "org-1"
    out = StringIO()

    call_command("migrate_ai_provider_settings", stdout=out)

    assert not AIProviderConfig.objects.exists()
    assert "Preview complete" in out.getvalue()
    assert "super-secret" not in out.getvalue()

    out = StringIO()
    call_command("migrate_ai_provider_settings", "--apply", stdout=out)

    provider = AIProviderConfig.objects.get(provider_type="openai")
    assert provider.api_key == "super-secret"
    assert provider.extra_settings == {"organization": "org-1"}
    assert list(provider.models.values_list("model_identifier", flat=True)) == [
        "gpt-4o",
        "gpt-4o-mini",
    ]
    assert "super-secret" not in out.getvalue()


@pytest.mark.django_db
def test_command_is_idempotent_and_preserves_existing_providers(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OPENAI_API_KEY = "environment-secret"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    existing = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-secret"
    )

    call_command("migrate_ai_provider_settings", "--apply", stdout=StringIO())
    call_command("migrate_ai_provider_settings", "--apply", stdout=StringIO())

    existing.refresh_from_db()
    assert existing.api_key == "database-secret"
    assert existing.models.count() == 0
    assert AIProviderConfig.objects.count() == 1


@pytest.mark.django_db
def test_command_reports_when_no_environment_settings_exist(settings):
    _clear_provider_environment(settings)
    out = StringIO()

    call_command("migrate_ai_provider_settings", stdout=out)
    output = out.getvalue()

    assert "nothing to import" in output
    assert "BASEROW_OPENAI_API_KEY" in output
    assert "BASEROW_OLLAMA_HOST" in output


@pytest.mark.django_db
def test_command_skips_incomplete_provider_settings(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OLLAMA_MODELS = ["llama3.3"]
    out = StringIO()

    call_command("migrate_ai_provider_settings", stdout=out)

    assert "Ollama: skipping" in out.getvalue()
    assert not AIProviderConfig.objects.exists()


@pytest.mark.django_db
def test_command_reports_preview_counts(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OPENAI_API_KEY = "secret"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4o"]
    settings.BASEROW_ANTHROPIC_API_KEY = "secret"
    settings.BASEROW_ANTHROPIC_MODELS = ["claude-sonnet"]
    AIProviderConfig.objects.create(provider_type="anthropic")
    out = StringIO()

    call_command("migrate_ai_provider_settings", stdout=out)

    assert "1 provider(s) to import, 1 left unchanged" in out.getvalue()
    assert "--apply" in out.getvalue()
