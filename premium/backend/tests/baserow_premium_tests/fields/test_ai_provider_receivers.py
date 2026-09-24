from collections.abc import Callable, Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.service import AIProviderService

MODEL_UNAVAILABLE_ERROR = "The selected AI model is disabled or no longer available."


@contextmanager
def capture_ai_field_broadcasts(
    django_capture_on_commit_callbacks: Callable,
) -> Iterator[tuple[MagicMock, MagicMock]]:
    with (
        patch(
            "baserow_premium.fields.receivers.page_registry.get"
        ) as page_registry_get,
        patch(
            "baserow.ws.signals.broadcast_ai_provider_update.delay"
        ) as broadcast_ai_provider_update,
        django_capture_on_commit_callbacks(execute=True),
    ):
        yield page_registry_get, broadcast_ai_provider_update


@pytest.mark.django_db
def test_instance_model_disable_does_not_broadcast_ai_field_errors(
    premium_data_fixture, django_capture_on_commit_callbacks
):
    user = premium_data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )
    for _ in range(2):
        premium_data_fixture.create_ai_field(
            table=premium_data_fixture.create_database_table(user=user),
            ai_generative_ai_type="openai",
            ai_generative_ai_model="gpt-5",
            ai_prompt="'Valid prompt'",
        )

    with capture_ai_field_broadcasts(django_capture_on_commit_callbacks) as (
        page_registry_get,
        broadcast_ai_provider_update,
    ):
        AIProviderService.update_model(user, provider.models.get().id, is_enabled=False)

    page_registry_get.assert_not_called()
    broadcast_ai_provider_update.assert_called_once_with(None, True)


@pytest.mark.django_db
def test_workspace_model_disable_broadcasts_only_that_workspace_ai_field_error(
    premium_data_fixture, django_capture_on_commit_callbacks
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    provider = AIProviderHandler.create_provider(
        "openai",
        workspace=workspace,
        api_key="secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-5",
        ai_prompt="'Valid prompt'",
    )
    premium_data_fixture.create_ai_field(
        table=premium_data_fixture.create_database_table(user=user),
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-5",
        ai_prompt="'Valid prompt'",
    )
    assert field.error is None

    with capture_ai_field_broadcasts(django_capture_on_commit_callbacks) as (
        page_registry_get,
        broadcast_ai_provider_update,
    ):
        AIProviderService.update_model(
            user,
            provider.models.get().id,
            workspace_id=workspace.id,
            is_enabled=False,
        )

    broadcast = page_registry_get.return_value.broadcast
    broadcast.assert_called_once()
    payload = broadcast.call_args.args[0]
    assert payload["type"] == "field_updated"
    assert payload["field_id"] == field.id
    assert payload["field"]["error"] == MODEL_UNAVAILABLE_ERROR
    assert broadcast.call_args.args[1] is None
    assert broadcast.call_args.kwargs["table_id"] == table.id
    broadcast_ai_provider_update.assert_called_once_with(workspace.id, True)


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_scope", [False, True])
def test_feature_setting_change_does_not_broadcast_untyped_ai_fields(
    premium_data_fixture, django_capture_on_commit_callbacks, workspace_scope
):
    user = premium_data_fixture.create_user(is_staff=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type=None,
        ai_generative_ai_model=None,
        ai_prompt="'Valid prompt'",
    )
    workspace_id = table.database.workspace_id if workspace_scope else None

    with capture_ai_field_broadcasts(django_capture_on_commit_callbacks) as (
        page_registry_get,
        broadcast_ai_provider_update,
    ):
        AIProviderService.update_feature_setting(
            user,
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_DISABLED,
            workspace_id=workspace_id,
        )

    page_registry_get.assert_not_called()
    broadcast_ai_provider_update.assert_called_once_with(workspace_id, True)


@pytest.mark.django_db
def test_provider_metadata_update_does_not_broadcast_ai_field_error(
    premium_data_fixture, django_capture_on_commit_callbacks
):
    user = premium_data_fixture.create_user(is_staff=True)
    table = premium_data_fixture.create_database_table(user=user)
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="old-secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-5",
        ai_prompt="'Valid prompt'",
    )

    with capture_ai_field_broadcasts(django_capture_on_commit_callbacks) as (
        page_registry_get,
        broadcast_ai_provider_update,
    ):
        AIProviderService.update_provider(
            user,
            provider.id,
            api_key="new-secret",
        )

    page_registry_get.assert_not_called()
    broadcast_ai_provider_update.assert_called_once_with(None, False)
