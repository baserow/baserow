import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync

from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.test_utils.helpers import AnyDict, AnyStr
from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
from baserow_enterprise.assistant.runs import ASSISTANT_RUN_TYPE


@pytest.fixture(autouse=True)
def model_check(mocker, settings) -> MagicMock:
    settings.FEATURE_FLAGS = ["assistant_background_runs"]
    mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._publish")
    mocker.patch("baserow.core.chat_runs.handler.notify_run_on_commit")
    mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._enqueue")
    return mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise"
    )


@pytest.fixture
def member(enterprise_data_fixture, enable_enterprise):
    user, token = enterprise_data_fixture.create_user_and_token()
    return user, token, enterprise_data_fixture.create_workspace(user=user)


def _url(chat_uuid):
    return reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid})


def _send(api_client, token, workspace, chat_uuid, content="Add a table"):
    return api_client.post(
        _url(chat_uuid),
        {
            "content": content,
            "ui_context": {
                "workspace": {"id": workspace.id, "name": workspace.name},
                "timezone": "Europe/Rome",
            },
            "tab_id": "tab-1",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="session-1",
    )


async def _initial_record(response):
    iterator = response.streaming_content
    try:
        return json.loads(await anext(iterator))
    finally:
        await iterator.aclose()


@pytest.mark.django_db
def test_the_existing_post_commits_and_streams_its_worker_backed_answer(
    api_client, member
):
    user, token, workspace = member
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    run = ChatRun.objects.get(id=response["X-Chat-Run-ID"])
    message = AssistantChatMessage.objects.get(chat__uuid=chat_uuid)
    record = async_to_sync(_initial_record)(response)
    assert record == {
        "type": "human",
        "id": message.id,
        "content": "Add a table",
        "timestamp": AnyStr(),
        "_run": {"id": str(run.id), "chat_id": message.chat_id, "status": "queued"},
    }
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
    snapshot = api_client.get(_url(chat_uuid), HTTP_AUTHORIZATION=f"JWT {token}").json()
    assert snapshot["active_run"]["human_message_id"] == message.id
    assert snapshot["latest_run"]["human_message_id"] == message.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "title,content,expected,generate",
    [
        ("", "Plan my\n  week", "Plan my week", True),
        ("", "x" * 100, "x" * 60, True),
        ("Tables", "Add a table", "Tables", False),
    ],
)
def test_a_new_chat_gets_a_provisional_title(
    api_client, member, title, content, expected, generate
):
    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace, title=title)
    response = _send(api_client, token, workspace, chat.uuid, content)
    chat.refresh_from_db()
    assert chat.title == expected
    assert (
        ChatRun.objects.get(id=response["X-Chat-Run-ID"]).context["generate_title"]
        is generate
    )


@pytest.mark.django_db
def test_a_second_message_preserves_the_draft_and_returns_existing_work(
    api_client, member
):
    _, token, workspace = member
    chat_uuid = uuid4()
    first = _send(api_client, token, workspace, chat_uuid)
    second = _send(api_client, token, workspace, chat_uuid, "And another")
    assert second.status_code == 409
    assert second.json()["run_id"] == first["X-Chat-Run-ID"]
    assert AssistantChatMessage.objects.filter(chat__uuid=chat_uuid).count() == 1


@pytest.mark.django_db
def test_a_user_cannot_exceed_the_active_run_cap(api_client, member):
    _, token, workspace = member
    for _ in range(2):
        assert _send(api_client, token, workspace, uuid4()).status_code == 200
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid)
    assert response.status_code == 429
    assert not AssistantChat.objects.filter(uuid=chat_uuid).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content,model_error,error",
    [
        ("a" * 100_001, None, "ERROR_REQUEST_BODY_VALIDATION"),
        (
            "Hi",
            AssistantModelNotSupportedError("down"),
            "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
        ),
    ],
    ids=["too-long", "unavailable-model"],
)
def test_a_refused_message_leaves_nothing_behind(
    api_client, member, model_check, content, model_error, error
):
    _, token, workspace = member
    model_check.side_effect = model_error
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid, content)
    assert response.status_code == 400
    assert response.json()["error"] == error
    assert not AssistantChat.objects.filter(uuid=chat_uuid).exists()
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_resume_only_attaches_without_message_or_task(api_client, member, mocker):
    _, token, workspace = member
    chat_uuid = uuid4()
    first = _send(api_client, token, workspace, chat_uuid)
    enqueue = mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._enqueue")
    model = mocker.patch(
        "baserow_enterprise.api.assistant.views.resolve_assistant_model"
    )
    response = api_client.post(
        _url(chat_uuid),
        {"run_id": first["X-Chat-Run-ID"], "tab_id": "tab-1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response["X-Chat-Run-ID"] == first["X-Chat-Run-ID"]
    assert AssistantChatMessage.objects.filter(chat__uuid=chat_uuid).count() == 1
    assert ChatRun.objects.count() == 1
    enqueue.assert_not_called()
    model.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra", [{"content": "Run again"}, {"ui_context": {}}, {"cursor": "broken"}]
)
def test_resume_rejects_new_work_or_invalid_cursor_before_200(
    api_client, member, extra
):
    _, token, workspace = member
    chat_uuid = uuid4()
    first = _send(api_client, token, workspace, chat_uuid)
    response = api_client.post(
        _url(chat_uuid),
        {"run_id": first["X-Chat-Run-ID"], **extra},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert AssistantChatMessage.objects.filter(chat__uuid=chat_uuid).count() == 1


@pytest.mark.django_db
def test_resume_cannot_follow_a_different_chat(api_client, member):
    user, token, workspace = member
    first = _send(api_client, token, workspace, uuid4())
    other = AssistantChat.objects.create(user=user, workspace=workspace)
    response = api_client.post(
        _url(other.uuid),
        {"run_id": first["X-Chat-Run-ID"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_remains_json_with_durable_active_and_latest_metadata(api_client, member):
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
    run = ChatRunHandler().create_run(ASSISTANT_RUN_TYPE, chat.id, workspace, user, {})
    busy = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")
    assert busy["Content-Type"] == "application/json"
    assert busy.json()["active_run"] == {
        "id": str(run.id),
        "chat_id": chat.id,
        "status": "queued",
        "human_message_id": None,
    }
    ChatRun.objects.filter(id=run.id).update(
        status=ChatRunStatus.COMPLETED,
        outcome={"type": "ai/message", "id": 123, "content": "Done"},
    )
    AssistantChat.objects.filter(id=chat.id).update(title="Finished title")
    ended = api_client.get(_url(chat.uuid), HTTP_AUTHORIZATION=f"JWT {token}")
    assert ended.json()["active_run"] is None
    assert ended.json()["latest_run"]["message"]["id"] == 123
    assert ended.json()["chat_title"] == "Finished title"
    assert ended.json()["latest_run"]["message"]["chat_title"] == "Finished title"


def test_the_original_post_uses_separate_async_follower_admission():
    from baserow.core.chat_runs.stream import _paths

    path = _url(uuid4())
    assert path.startswith("/assistant/chat/")
    assert any(
        "POST" in methods and pattern.fullmatch(path) for pattern, methods in _paths
    )
