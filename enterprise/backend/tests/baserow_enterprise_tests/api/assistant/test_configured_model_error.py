from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse

import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow_enterprise.assistant.exceptions import (
    AssistantConfiguredModelNotAvailableError,
)
from baserow_enterprise.assistant.models import AssistantChat


@pytest.mark.django_db
@patch(
    "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
    side_effect=AssistantConfiguredModelNotAvailableError("database model failed"),
)
def test_database_configured_model_failure_does_not_reference_legacy_environment(
    mock_check_lm,
    api_client,
    enterprise_data_fixture,
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()
    chat_uuid = uuid4()

    response = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
        "detail": (
            "The Kuma model selected in AI provider settings could not be used. "
            "Test the selected model and verify its provider credentials before "
            "trying again."
        ),
    }
    model_profile = mock_check_lm.call_args.kwargs["model_profile"]
    assert model_profile.workspace == workspace
    assert not AssistantChat.objects.filter(uuid=chat_uuid).exists()


@pytest.mark.django_db
def test_disabled_kuma_returns_a_disable_specific_chat_error(
    api_client,
    enterprise_data_fixture,
    settings,
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
        workspace=workspace,
    )
    chat_uuid = uuid4()

    response = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "ERROR_ASSISTANT_MODEL_DISABLED",
        "detail": (
            "Kuma is disabled in AI provider settings. Enable Kuma before trying again."
        ),
    }
    assert not AssistantChat.objects.filter(uuid=chat_uuid).exists()
