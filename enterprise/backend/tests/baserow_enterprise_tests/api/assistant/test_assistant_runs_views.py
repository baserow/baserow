import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.http.response import HttpResponseBase, StreamingHttpResponse
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync
from rest_framework.test import APIClient

from baserow.config import streaming
from baserow.core.chat_runs.constants import MAX_ACTIVE_RUNS_PER_USER
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.models import Workspace
from baserow.test_utils.helpers import AnyDict, AnyStr
from baserow_enterprise.assistant.assistant import assistant_message_payload
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
    AssistantChatPrediction,
)
from baserow_enterprise.assistant.runs import ASSISTANT_RUN_TYPE


@pytest.fixture(autouse=True)
def model_check(mocker) -> MagicMock:
    return mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise"
    )


@pytest.fixture(autouse=True)
def enqueue(mocker) -> MagicMock:
    """Stubs a started run's commit-time side effects; returns the enqueue mock."""

    mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._publish")
    mocker.patch("baserow.core.chat_runs.handler.notify_run_on_commit")
    return mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._enqueue")


@pytest.fixture
def member(
    enterprise_data_fixture, enable_enterprise
) -> tuple[AbstractUser, str, Workspace]:
    user, token = enterprise_data_fixture.create_user_and_token()
    return user, token, enterprise_data_fixture.create_workspace(user=user)


def _url(chat_uuid: UUID) -> str:
    return reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid})


def _send(
    api_client: APIClient,
    token: str,
    workspace: Workspace,
    chat_uuid: UUID,
    content: str = "Add a table",
    ui_context: dict[str, Any] | None = None,
    session_id: str = "session-1",
) -> HttpResponseBase:
    ui_context = ui_context or {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "timezone": "Europe/Rome",
    }
    return api_client.post(
        _url(chat_uuid),
        {"content": content, "ui_context": ui_context, "tab_id": "tab-1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=session_id,
    )


async def _initial_record(response: StreamingHttpResponse) -> dict[str, Any]:
    iterator = response.streaming_content
    try:
        return json.loads(await anext(iterator))
    finally:
        await iterator.aclose()


def _run_id(response: StreamingHttpResponse) -> str:
    return async_to_sync(_initial_record)(response)["_run"]["id"]


@pytest.mark.django_db
def test_sending_saves_the_message_and_enqueues_its_run(
    api_client, member, enqueue, django_capture_on_commit_callbacks
):
    user, token, workspace = member
    chat_uuid = uuid4()
    with django_capture_on_commit_callbacks(execute=True):
        response = _send(api_client, token, workspace, chat_uuid)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"
    record = async_to_sync(_initial_record)(response)
    run = ChatRun.objects.get(id=record["_run"]["id"])
    message = AssistantChatMessage.objects.get(chat__uuid=chat_uuid)
    assert record == {
        "type": "human",
        "id": message.id,
        "content": "Add a table",
        "timestamp": AnyStr(),
        "_run": {"id": str(run.id), "chat_id": message.chat_id, "status": "queued"},
    }
    enqueue.assert_called_once_with(run.id)
    assert run.created_by == user
    assert run.context == {
        "human_message_id": message.id,
        "client_session_id": "session-1",
        "action_group_id": AnyStr(),
        "ui_context": AnyDict(),
        "origin_tab_id": "tab-1",
        "generate_title": True,
    }
    assert UUID(run.context["action_group_id"]).version == 4
    assert run.context["ui_context"]["timezone"] == "Europe/Rome"


@pytest.mark.django_db
def test_an_old_tab_can_send_without_run_metadata(api_client, member):
    _, token, workspace = member
    response = api_client.post(
        _url(uuid4()),
        {
            "content": "Hello",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    run = ChatRun.objects.get(id=_run_id(response))
    assert run.context["origin_tab_id"] == ""
    assert AssistantChatMessage.objects.get(chat_id=run.chat_id).content == "Hello"


TRUNCATED_TITLE = "Plan my week " + "x" * 47


@pytest.mark.django_db
@pytest.mark.parametrize(
    "title,first,content,expected,generate",
    [
        ("", None, "Plan my\n  week", "Plan my week", True),
        ("", None, "x" * 100, "x" * 60, True),
        ("Tables", "Plan my week", "Add a table", "Tables", False),
        (TRUNCATED_TITLE, "Plan my\n  week " + "x" * 60, "Hi", TRUNCATED_TITLE, True),
    ],
    ids=["untitled", "long", "generated", "still_provisional"],
)
def test_runs_generate_a_title_until_the_chat_has_one(
    api_client, member, title, first, content, expected, generate
):
    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace, title=title)
    if first:
        chat.messages.create(role=AssistantChatMessage.Role.HUMAN, content=first)
    response = _send(api_client, token, workspace, chat.uuid, content)
    chat.refresh_from_db()
    assert chat.title == expected
    assert (
        ChatRun.objects.get(id=_run_id(response)).context["generate_title"] is generate
    )


@pytest.mark.django_db
def test_a_message_sent_during_a_run_is_refused(api_client, member):
    _, token, workspace = member
    chat_uuid = uuid4()
    _send(api_client, token, workspace, chat_uuid)
    second = _send(api_client, token, workspace, chat_uuid, "And another")
    assert second.status_code == 409
    assert second.json()["error"] == "ERROR_CHAT_RUN_IN_PROGRESS"
    assert AssistantChatMessage.objects.filter(chat__uuid=chat_uuid).count() == 1


@pytest.mark.django_db
def test_a_user_cannot_exceed_the_active_run_cap(api_client, member):
    _, token, workspace = member
    for _ in range(MAX_ACTIVE_RUNS_PER_USER):
        assert _send(api_client, token, workspace, uuid4()).status_code == 200
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid)
    assert response.status_code == 429
    assert not AssistantChat.objects.filter(uuid=chat_uuid).exists()


@pytest.mark.django_db
def test_sending_does_not_add_a_new_message_length_limit(api_client, member):
    _, token, workspace = member
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid, "a" * 100_001)
    assert response.status_code == 200
    run = ChatRun.objects.get(id=_run_id(response))
    assert (
        AssistantChatMessage.objects.get(chat_id=run.chat_id).content == "a" * 100_001
    )


@pytest.mark.django_db
def test_core_stream_follows_kuma_with_its_permissions(
    api_client, member, enterprise_data_fixture
):
    _, token, workspace = member
    run_id = _run_id(_send(api_client, token, workspace, uuid4()))
    ChatRunHandler().request_cancel(UUID(run_id))
    url = reverse("api:chat_runs:stream", kwargs={"run_id": run_id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200
    record = async_to_sync(_initial_record)(response)
    assert record["kind"] == "run.finished"
    assert record["data"]["id"] == run_id
    assert record["data"]["status"] == ChatRunStatus.CANCELLED
    assert record["data"]["message"]["type"] == "ai/message"
    assert ChatRun.objects.count() == 1
    assert AssistantChatMessage.objects.filter(role="human").count() == 1

    _, other_token = enterprise_data_fixture.create_user_and_token()
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {other_token}")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body,missing", [({}, "content"), ({"content": "Hi"}, "ui_context")]
)
def test_a_post_requires_a_new_message(api_client, member, body, missing):
    _, token, _ = member
    response = api_client.post(
        _url(uuid4()), body, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"][missing][0]["code"] == "required"
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_get_returns_the_active_and_latest_run(api_client, member):
    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    idle = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")
    assert idle.json() == {
        "chat_id": chat.id,
        "chat_title": "",
        "messages": [],
        "active_run": None,
        "latest_run": None,
    }
    run = ChatRunHandler().create_run(
        ASSISTANT_RUN_TYPE, chat.id, workspace, user, {"human_message_id": 7}
    )
    busy = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")
    assert busy.json()["latest_run"] == busy.json()["active_run"]
    assert busy.json()["active_run"] == {
        "id": str(run.id),
        "run_type": ASSISTANT_RUN_TYPE,
        "chat_id": chat.id,
        "status": "queued",
        "error_code": "",
        "cancel_requested_at": None,
        "message": None,
        "human_message_id": 7,
    }
    ChatRun.objects.filter(id=run.id).update(
        status=ChatRunStatus.COMPLETED,
        outcome={"type": "ai/message", "id": 123, "content": "Done"},
    )
    ended = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")
    assert ended.json()["active_run"] is None
    assert ended.json()["latest_run"]["message"]["id"] == 123
    assert ended.json()["latest_run"]["human_message_id"] == 7


@pytest.mark.django_db
def test_a_reloaded_chat_shows_how_each_answer_ended(api_client, member):
    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    human = chat.messages.create(role=AssistantChatMessage.Role.HUMAN, content="Hi")
    stopped = chat.messages.create(
        role=AssistantChatMessage.Role.AI,
        content="Partial",
        artifacts={
            "sources": ["https://baserow.io/docs"],
            "run": {"status": "failed", "error_code": "interrupted"},
        },
    )
    AssistantChatPrediction.objects.create(human_message=human, ai_response=stopped)
    chat.messages.create(role=AssistantChatMessage.Role.AI, content="Done")

    response = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")

    saved = chat.messages.select_related("prediction").order_by("id")
    messages = response.json()["messages"]
    assert messages == [assistant_message_payload(message) for message in saved]
    assert messages[1] == {
        "id": stopped.id,
        "type": "ai/message",
        "content": "Partial",
        "timestamp": AnyStr(),
        "sources": ["https://baserow.io/docs"],
        "can_submit_feedback": True,
        "human_sentiment": None,
        "run_status": "failed",
        "error_code": "interrupted",
        "onboarding_target": None,
    }
    assert (messages[2]["run_status"], messages[2]["error_code"]) == (None, None)


def test_message_posts_are_served_by_the_async_stream_router():
    router = streaming.AsyncStreamingHTTPRouter(MagicMock(), max_streams=100)
    assert any(
        "POST" in methods and pattern.fullmatch(_url(uuid4()))
        for pattern, methods in router.paths
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "context",
    [
        {},
        {
            "database": {"id": "123", "name": "My Database"},
            "table": {"id": 456, "name": "Customers"},
            "view": {"id": 789, "name": "All Customers", "type": "grid"},
        },
        {
            "application": {"id": "app-123", "name": "My App"},
            "page": {"id": "page-456", "name": "Dashboard"},
        },
        {
            "automation": {"id": "auto-123", "name": "Customer Automation"},
            "workflow": {"id": "wf-456", "name": "Send Email Workflow"},
        },
        {"dashboard": {"id": "dash-789", "name": "Sales Dashboard"}},
    ],
    ids=["workspace-only", "database", "application", "automation", "dashboard"],
)
def test_sending_preserves_ui_context_for_the_worker(api_client, member, context):
    _, token, workspace = member
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        **context,
    }
    response = _send(api_client, token, workspace, uuid4(), ui_context=ui_context)
    assert response.status_code == 200
    saved = ChatRun.objects.get(id=_run_id(response)).context["ui_context"]
    for key, value in ui_context.items():
        assert saved[key] == value


@pytest.mark.django_db
def test_invalid_session_id_cannot_create_a_chat_or_run(api_client, member):
    _, token, workspace = member
    response = _send(
        api_client, token, workspace, uuid4(), session_id="invalid session"
    )
    assert response.status_code == 400
    assert "An invalid ClientSessionId header was provided." in response.json()[0]
    assert not AssistantChat.objects.exists()
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_cancel_stops_the_chats_active_run(api_client, member):
    _, token, workspace = member
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid)
    run = ChatRun.objects.get(id=_run_id(response))

    response = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat_uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    run.refresh_from_db()
    assert run.status == ChatRunStatus.CANCELLED


@pytest.mark.django_db
def test_stop_keeps_the_old_http_cancellation_signal(api_client, member, settings):
    settings.BASEROW_USE_LOCAL_CACHE = True

    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    response = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat.uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert not ChatRun.objects.exists()
    assert cache.get(f"assistant:chat:{chat.uuid}:cancelled") is True
