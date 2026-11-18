from unittest.mock import patch

from django.core.management import CommandError, call_command

import pytest

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.populate import load_test_ai_provider, load_test_data


@pytest.mark.django_db
def test_populate_without_opt_in(settings):
    settings.BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE = ""
    settings.BASEROW_OPENAI_API_KEY = "legacy-key"
    load_test_ai_provider()
    assert not AIProviderConfig.objects.exists()


@pytest.mark.django_db
def test_populate_openai_from_file(settings, tmp_path, data_fixture, capsys):
    """Exercise the command's core loader, inheritance, and repeat population."""

    key_file = tmp_path / "key"
    key_file.write_text("  test-secret\n")
    settings.BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE = str(key_file)
    settings.DEBUG = True
    workspace = data_fixture.create_workspace()
    with (
        patch(
            "baserow.core.management.commands.populate_test_data.Command.available_modules",
            return_value={"core": load_test_data},
        ),
        patch("socket.socket.connect", side_effect=AssertionError("Network call")),
    ):
        call_command("populate_test_data")
        key_file.write_text("replacement-secret")
        call_command("populate_test_data")

    provider = AIProviderConfig.objects.get()
    assert provider.workspace_id is None
    assert provider.provider_type == "openai"
    assert provider.api_key == "test-secret"
    assert provider.is_active
    assert not provider.models.exists()
    inherited = AIProviderHandler.list_providers(workspace=workspace)
    assert [(item.id, item.read_only) for item in inherited] == [(provider.id, True)]
    assert "test-secret" not in capsys.readouterr().out


@pytest.mark.django_db
def test_populate_preserves_existing_provider(settings):
    """Even disabled providers and their models survive an unavailable key file."""

    provider = AIProviderHandler.create_provider(
        "openai", api_key="existing", models_data=[{"model_identifier": "custom-model"}]
    )
    AIProviderHandler.update_provider(provider, is_active=False)
    settings.BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE = "/missing/key"
    load_test_ai_provider()
    provider.refresh_from_db()
    assert provider.api_key == "existing"
    assert not provider.is_active
    assert list(provider.models.values_list("model_identifier", flat=True)) == [
        "custom-model"
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("contents", [None, " \n", b"\xff"])
def test_populate_rejects_invalid_key_file(settings, tmp_path, contents):
    key_file = tmp_path / "key"
    if isinstance(contents, bytes):
        key_file.write_bytes(contents)
    elif contents is not None:
        key_file.write_text(contents)
    settings.BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE = str(key_file)
    with pytest.raises(CommandError, match="BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE"):
        load_test_ai_provider()
    assert not AIProviderConfig.objects.exists()


@pytest.mark.django_db
def test_populate_keeps_workspace_provider(settings, tmp_path, data_fixture):
    """A workspace-owned OpenAI provider does not prevent instance population."""

    owned = AIProviderHandler.create_provider(
        "openai", api_key="workspace-secret", workspace=data_fixture.create_workspace()
    )
    key_file = tmp_path / "key"
    key_file.write_text("instance-secret")
    settings.BASEROW_DEV_POPULATE_OPENAI_API_KEY_FILE = str(key_file)
    load_test_ai_provider()
    owned.refresh_from_db()
    assert owned.api_key == "workspace-secret"
    assert AIProviderConfig.objects.get(workspace=None).api_key == "instance-secret"
    assert AIProviderConfig.objects.count() == 2
