from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

import pytest

from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.generative_ai.registries import generative_ai_model_type_registry


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

    call_command("migrate_ai_provider_settings", "--scope", "instance", stdout=out)

    assert not AIProviderConfig.objects.exists()
    assert "Preview complete" in out.getvalue()
    assert "super-secret" not in out.getvalue()

    out = StringIO()
    call_command(
        "migrate_ai_provider_settings",
        "--scope",
        "instance",
        "--apply",
        stdout=out,
    )

    provider = AIProviderConfig.objects.get(provider_type="openai")
    assert provider.api_key == "super-secret"
    assert provider.extra_settings == {"organization": "org-1"}
    assert list(provider.models.values_list("model_identifier", flat=True)) == [
        "gpt-4o",
        "gpt-4o-mini",
    ]
    assert "Imported 1 missing instance provider(s)." in out.getvalue()
    assert "super-secret" not in out.getvalue()


@pytest.mark.django_db
def test_command_is_idempotent_and_preserves_existing_providers(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OPENAI_API_KEY = "environment-secret"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    existing = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-secret"
    )

    call_command(
        "migrate_ai_provider_settings",
        "--scope",
        "instance",
        "--apply",
        stdout=StringIO(),
    )
    call_command(
        "migrate_ai_provider_settings",
        "--scope",
        "instance",
        "--apply",
        stdout=StringIO(),
    )

    existing.refresh_from_db()
    assert existing.api_key == "database-secret"
    assert existing.models.count() == 0
    assert AIProviderConfig.objects.count() == 1


@pytest.mark.django_db
def test_command_reports_when_no_environment_settings_exist(settings):
    _clear_provider_environment(settings)
    out = StringIO()

    call_command("migrate_ai_provider_settings", "--scope", "instance", stdout=out)
    output = out.getvalue()

    assert "nothing to import" in output
    assert "BASEROW_OPENAI_API_KEY" in output
    assert "BASEROW_OLLAMA_HOST" in output


@pytest.mark.django_db
def test_command_skips_incomplete_provider_settings(settings):
    _clear_provider_environment(settings)
    settings.BASEROW_OLLAMA_MODELS = ["llama3.3"]
    out = StringIO()

    call_command("migrate_ai_provider_settings", "--scope", "instance", stdout=out)

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

    call_command("migrate_ai_provider_settings", "--scope", "instance", stdout=out)

    assert "1 provider(s) to import, 1 left unchanged" in out.getvalue()
    assert "--apply" in out.getvalue()


@pytest.mark.django_db
def test_workspace_scope_previews_then_imports_idempotently_without_secrets(
    data_fixture,
):
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {
                "api_key": "workspace-secret",
                "models": ["gpt-5.4", "gpt-5.4-mini"],
                "organization": "workspace-org",
            }
        }
    )

    preview = StringIO()
    call_command("migrate_ai_provider_settings", "--scope", "workspace", stdout=preview)

    assert not AIProviderConfig.objects.exists()
    assert "2 model(s)" in preview.getvalue()
    assert "workspace-secret" not in preview.getvalue()

    for _ in range(2):
        call_command(
            "migrate_ai_provider_settings",
            "--scope",
            "workspace",
            "--apply",
            stdout=StringIO(),
        )

    provider = AIProviderConfig.objects.get(workspace=workspace, provider_type="openai")
    assert provider.api_key == "workspace-secret"
    assert provider.extra_settings == {"organization": "workspace-org"}
    assert list(provider.models.values_list("model_identifier", flat=True)) == [
        "gpt-5.4",
        "gpt-5.4-mini",
    ]
    workspace.refresh_from_db()
    assert workspace.generative_ai_models_settings["openai"]["api_key"] == (
        "workspace-secret"
    )

    AIProviderHandler.delete_provider(provider)
    workspace.refresh_from_db()
    assert "openai" not in workspace.generative_ai_models_settings


@pytest.mark.django_db
def test_workspace_scope_migrates_every_current_legacy_provider_setting(
    data_fixture, settings
):
    legacy_settings = {
        "openai": {
            "api_key": "openai-key",
            "models": ["gpt-5.4", "gpt-5.4-mini"],
            "organization": "openai-org",
            "base_url": "https://openai.example/v1",
        },
        "anthropic": {
            "api_key": "anthropic-key",
            "models": ["claude-sonnet-4-6"],
        },
        "mistral": {
            "api_key": "mistral-key",
            "models": ["mistral-large-latest"],
        },
        "ollama": {
            "models": ["llama3.3", "qwen3"],
            "host": "https://ollama.example",
        },
        "openrouter": {
            "api_key": "openrouter-key",
            "models": ["openai/gpt-5.4"],
            "organization": "openrouter-org",
        },
    }
    expected_extra_settings = {
        "openai": {
            "organization": "openai-org",
            "base_url": "https://openai.example/v1",
        },
        "anthropic": {},
        "mistral": {},
        "ollama": {"host": "https://ollama.example"},
        "openrouter": {"organization": "openrouter-org"},
    }
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings=legacy_settings
    )

    call_command(
        "migrate_ai_provider_settings",
        "--scope",
        "workspace",
        "--apply",
        stdout=StringIO(),
    )

    assert AIProviderConfig.objects.filter(workspace=workspace).count() == len(
        legacy_settings
    )
    settings.FEATURE_FLAGS = ["ai-providers"]
    for provider_type, legacy_values in legacy_settings.items():
        provider = AIProviderConfig.objects.get(
            workspace=workspace, provider_type=provider_type
        )
        expected_api_key = legacy_values.get("api_key", "")
        expected_models = legacy_values["models"]
        expected_extra = expected_extra_settings[provider_type]

        assert provider.api_key == expected_api_key
        assert provider.extra_settings == expected_extra
        assert (
            list(provider.models.values_list("model_identifier", flat=True))
            == expected_models
        )

        model_type = generative_ai_model_type_registry.get(provider_type)
        assert model_type.get_model_settings_override(
            expected_models[0], workspace
        ) == {
            "api_key": expected_api_key,
            "models": expected_models,
            **expected_extra,
        }

    workspace.refresh_from_db()
    assert workspace.generative_ai_models_settings == legacy_settings


@pytest.mark.django_db
def test_workspace_scope_keeps_conflicts_and_reports_invalid_settings(data_fixture):
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"models": ["legacy-model"]},
            "anthropic": {
                "api_key": "legacy-anthropic-key",
                "models": ["legacy-claude"],
            },
            "mistral": "invalid-settings",
        }
    )
    existing = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="anthropic",
        api_key="database-key",
    )

    output = StringIO()
    call_command(
        "migrate_ai_provider_settings",
        "--scope",
        "workspace",
        "--apply",
        stdout=output,
    )

    assert AIProviderConfig.objects.filter(workspace=workspace).count() == 1
    existing.refresh_from_db()
    assert existing.api_key == "database-key"
    assert output.getvalue().count("skipping incomplete legacy settings") == 2
    assert "keeping existing database configuration" in output.getvalue()


@pytest.mark.django_db
def test_workspace_scope_import_is_atomic(data_fixture):
    data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"api_key": "openai-key", "models": ["gpt-5.4"]},
            "anthropic": {
                "api_key": "anthropic-key",
                "models": ["claude-sonnet-4-6"],
            },
        }
    )
    create_provider = AIProviderHandler.create_provider

    def create_provider_then_fail(*args, **kwargs):
        provider = create_provider(*args, **kwargs)
        if kwargs["provider_type"] == "anthropic":
            raise RuntimeError("stop after creating the second provider")
        return provider

    with (
        patch.object(
            AIProviderHandler,
            "create_provider",
            side_effect=create_provider_then_fail,
        ),
        pytest.raises(RuntimeError),
    ):
        call_command(
            "migrate_ai_provider_settings",
            "--scope",
            "workspace",
            "--apply",
            stdout=StringIO(),
        )

    assert not AIProviderConfig.objects.exists()
