from unittest.mock import patch

import pytest

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.service import AIProviderService
from baserow.core.handler import CoreHandler


@pytest.mark.django_db
def test_disabling_model_broadcasts_updated_ai_field_error(
    settings, premium_data_fixture, django_capture_on_commit_callbacks
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    user = premium_data_fixture.create_user(is_staff=True)
    table = premium_data_fixture.create_database_table(user=user)
    table.database.workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-secret",
            "models": ["gpt-5"],
        }
    }
    table.database.workspace.save(update_fields=("generative_ai_models_settings",))
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-5",
        ai_prompt="'Valid prompt'",
    )
    assert field.error is None

    with (
        patch(
            "baserow_premium.fields.receivers.page_registry.get"
        ) as page_registry_get,
        django_capture_on_commit_callbacks(execute=True),
    ):
        AIProviderService.update_model(user, provider.models.get().id, is_enabled=False)

    broadcast = page_registry_get.return_value.broadcast
    broadcast.assert_called_once()
    payload = broadcast.call_args.args[0]
    assert payload["type"] == "field_updated"
    assert payload["field_id"] == field.id
    assert payload["field"]["error"] == (
        "The selected AI model is disabled or no longer available."
    )
    assert broadcast.call_args.args[1] is None


@pytest.mark.django_db
def test_workspace_ai_settings_change_broadcasts_updated_ai_field_error(
    settings, premium_data_fixture, django_capture_on_commit_callbacks
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    user = premium_data_fixture.create_user(is_staff=True)
    table = premium_data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-secret",
            "models": ["gpt-5"],
        }
    }
    workspace.save(update_fields=("generative_ai_models_settings",))
    AIProviderHandler.create_provider(
        "openai",
        api_key="secret",
        models_data=[
            {"model_identifier": "gpt-5"},
            {"model_identifier": "gpt-4"},
        ],
    )
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-5",
        ai_prompt="'Valid prompt'",
    )
    assert field.error is None

    with (
        patch(
            "baserow_premium.fields.receivers.page_registry.get"
        ) as page_registry_get,
        patch("baserow.ws.signals.broadcast_to_group"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        locked_workspace = CoreHandler().get_workspace_for_update(workspace.id)
        CoreHandler().update_workspace(
            user,
            locked_workspace,
            generative_ai_models_settings={
                "openai": {
                    "api_key": "workspace-secret",
                    "models": ["gpt-4"],
                }
            },
        )

    broadcast = page_registry_get.return_value.broadcast
    broadcast.assert_called_once()
    payload = broadcast.call_args.args[0]
    assert payload["type"] == "field_updated"
    assert payload["field_id"] == field.id
    assert payload["field"]["error"] == (
        "The selected AI model is disabled or no longer available."
    )
