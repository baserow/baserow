from typing import Any, Callable, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.models.function import FunctionModel

from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow_enterprise.assistant.assistant import BackgroundAssistant
from baserow_enterprise.assistant.model_profiles import resolve_assistant_model
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
from baserow_enterprise.assistant.runs import ASSISTANT_RUN_TYPE
from baserow_enterprise.assistant.types import (
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

SESSION_ID = "s" * 256


@pytest.fixture
def posthog_client(mocker) -> MagicMock:
    client = MagicMock()
    mocker.patch(
        "baserow_enterprise.assistant.telemetry.get_posthog_client",
        return_value=client,
    )
    return client


@pytest.fixture
def output_events(mocker) -> list[dict[str, Any]]:
    """Observe the adapter's output without depending on a shared Redis server."""

    events = []

    async def append(buffer, batch):
        appended = [{"kind": kind, "data": data} for kind, data in batch]
        events.extend(appended)
        return appended

    mocker.patch("baserow.core.chat_runs.buffer.ChatRunBuffer.append", append)
    mocker.patch("baserow.core.chat_runs.handler.notify_run_on_commit")
    return events


@pytest.fixture
def fast_journal(monkeypatch) -> None:
    monkeypatch.setattr(
        "baserow.core.chat_runs.journal.LEASE_RENEW_INTERVAL_SECONDS", 0.01
    )
    monkeypatch.setattr("baserow.core.chat_runs.journal.FLUSH_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def assistant_run(
    enterprise_data_fixture, posthog_client, output_events, assistant_test_model
) -> Callable[..., ChatRun]:
    """
    Creates a chat, its human message and the queued run answering it. Runs use
    the test model, and report to a mock PostHog client and output buffer.
    """

    def _assistant_run(
        content: str = "Add a table",
        title: str = "Tables",
        context: Optional[dict[str, Any]] = None,
    ) -> ChatRun:
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(user=user, workspace=workspace, title=title)
        human_message = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content=content
        )
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext.from_user(user),
            timezone="Europe/Rome",
        )
        return ChatRunHandler().create_run(
            ASSISTANT_RUN_TYPE,
            chat.id,
            workspace,
            user,
            {
                "human_message_id": human_message.id,
                "client_session_id": SESSION_ID,
                "action_group_id": str(uuid4()),
                "ui_context": ui_context.model_dump(mode="json"),
                "origin_tab_id": "tab-1",
                "generate_title": False,
                **(context or {}),
            },
        )

    return _assistant_run


@pytest.fixture
def assistant_test_model(settings) -> None:
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


@pytest.fixture
def kuma_model(mocker) -> Callable[..., FunctionModel]:
    """Makes Kuma's runs use a scripted model whose readiness check passes."""

    mocker.patch("baserow_enterprise.assistant.chat_run_type.check_lm_ready_or_raise")

    def _kuma_model(
        stream_function: Callable[..., Any],
        function: Optional[Callable[..., Any]] = None,
    ) -> FunctionModel:
        model = FunctionModel(function=function, stream_function=stream_function)
        mocker.patch(
            "baserow_enterprise.assistant.model_profiles."
            "ResolvedAssistantModelProfile.create_model",
            return_value=model,
        )
        return model

    return _kuma_model


@pytest.fixture
def background_assistant(assistant_run) -> BackgroundAssistant:
    """The assistant of a queued run, reporting to a mock journal."""

    chat = AssistantChat.objects.select_related("workspace", "user__profile").get(
        id=assistant_run().chat_id
    )
    model_profile = resolve_assistant_model(workspace=chat.workspace)
    return BackgroundAssistant(chat, model_profile, MagicMock(), "tab-1")
