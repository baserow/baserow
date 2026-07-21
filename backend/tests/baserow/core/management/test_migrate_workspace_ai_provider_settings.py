from io import StringIO

from django.core.management import call_command

import pytest

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig


@pytest.mark.django_db
def test_workspace_provider_import_is_previewed_and_applied_idempotently(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-secret",
            "models": ["gpt-5.4", "gpt-5.4-mini"],
            "organization": "workspace-org",
        }
    }
    workspace.save(update_fields=("generative_ai_models_settings",))

    preview = StringIO()
    call_command("migrate_workspace_ai_provider_settings", stdout=preview)

    assert not AIProviderConfig.objects.exists()
    assert "2 model(s)" in preview.getvalue()
    assert "workspace-secret" not in preview.getvalue()

    call_command("migrate_workspace_ai_provider_settings", "--apply", stdout=StringIO())
    call_command("migrate_workspace_ai_provider_settings", "--apply", stdout=StringIO())

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
def test_workspace_provider_import_keeps_conflicts_and_incomplete_settings(
    data_fixture,
):
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"models": ["legacy-model"]},
            "anthropic": {
                "api_key": "legacy-anthropic-key",
                "models": ["legacy-claude"],
            },
        }
    )
    existing = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="anthropic",
        api_key="database-key",
    )

    output = StringIO()
    call_command("migrate_workspace_ai_provider_settings", "--apply", stdout=output)

    assert AIProviderConfig.objects.filter(workspace=workspace).count() == 1
    existing.refresh_from_db()
    assert existing.api_key == "database-key"
    assert "skipping incomplete legacy settings" in output.getvalue()
    assert "keeping existing database configuration" in output.getvalue()
