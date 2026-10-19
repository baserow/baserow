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
    settings.FEATURE_FLAGS = []
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


def _run_id(response):
    return async_to_sync(_initial_record)(response)["_run"]["id"]


@pytest.mark.django_db
def test_the_existing_post_commits_and_streams_its_worker_backed_answer(
    api_client, member, mocker, model_check, django_capture_on_commit_callbacks
):
    user, token, workspace = member
    chat_uuid = uuid4()
    enqueue = mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._enqueue")
    assistant = mocker.patch(
        "baserow_enterprise.assistant.handler.AssistantHandler.get_assistant"
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = _send(api_client, token, workspace, chat_uuid)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
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
    assistant.assert_not_called()
    assert model_check.call_args.kwargs["model_profile"].workspace == workspace
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
        ChatRun.objects.get(id=_run_id(response)).context["generate_title"] is generate
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
    assert second.json()["run_id"] == _run_id(first)
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
    run_id = _run_id(first)
    enqueue = mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler._enqueue")
    model = mocker.patch(
        "baserow_enterprise.api.assistant.views.resolve_assistant_model"
    )
    response = api_client.post(
        _url(chat_uuid),
        {"run_id": run_id, "tab_id": "tab-1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert _run_id(response) == run_id
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
        {"run_id": _run_id(first), **extra},
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
        {"run_id": _run_id(first)},
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
    from baserow.config.streaming import _paths

    path = _url(uuid4())
    assert path.startswith("/assistant/chat/")
    assert any(
        "POST" in methods and pattern.fullmatch(path) for pattern, methods in _paths
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
    user, token, workspace = member
    chat_uuid = uuid4()
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        **context,
    }
    response = api_client.post(
        _url(chat_uuid),
        {"content": "Help with this page", "ui_context": ui_context},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    saved = ChatRun.objects.get(id=_run_id(response)).context["ui_context"]
    for key, value in ui_context.items():
        assert saved[key] == value
    assert saved["user"] == {
        "id": user.id,
        "name": user.first_name,
        "email": user.email,
    }
    assert saved["timezone"] == "UTC"


@pytest.mark.django_db
def test_invalid_session_id_cannot_create_a_chat_or_run(api_client, member):
    _, token, workspace = member
    response = api_client.post(
        _url(uuid4()),
        {
            "content": "Help me",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="invalid session",
    )
    assert response.status_code == 400
    assert "An invalid ClientSessionId header was provided." in response.json()[0]
    assert not AssistantChat.objects.exists()
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_post_keeps_json_record_framing_for_worker_output(api_client, member, mocker):
    _, token, workspace = member
    events = [
        {"kind": "progress", "data": {"text": "Searching documentation..."}},
        {"kind": "text.delta", "data": {"segment": 0, "text": "Hello"}},
        {"kind": "text.delta", "data": {"segment": 0, "text": " world"}},
        {"kind": "chat.title", "data": {"title": "A greeting"}},
        {
            "kind": "run.finished",
            "data": {
                "status": "completed",
                "message": {
                    "type": "ai/message",
                    "id": 123,
                    "content": "Hello world",
                    "sources": ["https://baserow.io/user-docs"],
                },
            },
        },
    ]

    async def follow(*args, **kwargs):
        for index, event in enumerate(events):
            yield {**event, "cursor": f"cursor-{index}"}

    mocker.patch("baserow_enterprise.assistant.stream.follow_run", side_effect=follow)
    response = _send(api_client, token, workspace, uuid4())
    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"
    chunks = response.stream_chunks()
    assert all(chunk.endswith(b"\n\n") for chunk in chunks)
    records = [json.loads(chunk) for chunk in chunks]
    assert [record["type"] for record in records] == [
        "human",
        "ai/started",
        "ai/thinking",
        "ai/message",
        "ai/message",
        "chat/title",
        "ai/message",
    ]
    assert [records[index]["content"] for index in (2, 3, 4, 5)] == [
        "Searching documentation...",
        "Hello",
        "Hello world",
        "A greeting",
    ]
    assert records[-1]["id"] == 123
    assert records[-1]["sources"] == ["https://baserow.io/user-docs"]
    assert records[-1]["_run"]["status"] == "completed"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,kind", [("cancelled", "ai/cancelled"), ("failed", "ai/error")]
)
def test_post_keeps_terminal_error_and_cancel_records(
    api_client, member, mocker, status, kind
):
    _, token, workspace = member

    async def follow(*args, **kwargs):
        yield {
            "kind": "run.finished",
            "cursor": "last",
            "data": {"status": status, "error_code": "interrupted"},
        }

    mocker.patch("baserow_enterprise.assistant.stream.follow_run", side_effect=follow)
    response = _send(api_client, token, workspace, uuid4())
    records = [json.loads(chunk) for chunk in response.stream_chunks()]
    assert records[-2]["_run"]["status"] == status
    assert records[-1]["type"] == kind
    if status == "failed":
        assert records[-1]["code"] == "interrupted"


@pytest.mark.django_db
def test_disconnecting_closes_only_the_output_follower(api_client, member, mocker):
    _, token, workspace = member
    lifecycle = []

    async def stream(*args, **kwargs):
        try:
            yield '{"type": "ai/message", "content": "Hello"}\n\n'
        finally:
            lifecycle.append("follower-closed")

    mocker.patch(
        "baserow_enterprise.api.assistant.views.stream_run_messages", side_effect=stream
    )
    response = _send(api_client, token, workspace, uuid4())

    async def consume_one_chunk_and_close():
        iterator = aiter(response)
        chunk = await anext(iterator)
        await iterator.aclose()
        return chunk

    chunk = async_to_sync(consume_one_chunk_and_close)()
    assert json.loads(chunk)["content"] == "Hello"
    assert lifecycle == ["follower-closed"]
    run = ChatRun.objects.get()
    assert run.status == ChatRunStatus.QUEUED
    assert run.cancel_requested_at is None


@pytest.mark.django_db
@pytest.mark.parametrize("started", [False, True], ids=["queued", "running"])
def test_the_existing_cancel_endpoint_always_cancels_durable_work(
    api_client, member, started
):
    _, token, workspace = member
    chat_uuid = uuid4()
    response = _send(api_client, token, workspace, chat_uuid)
    run = ChatRun.objects.get(id=_run_id(response))
    if started:
        ChatRunHandler().claim_run(run.id)

    response = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat_uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    run.refresh_from_db()
    if started:
        assert run.status == ChatRunStatus.RUNNING
        assert run.cancel_requested_at is not None
    else:
        assert run.status == ChatRunStatus.CANCELLED


@pytest.mark.django_db
def test_cancelling_an_idle_chat_is_harmless(api_client, member):
    user, token, workspace = member
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    response = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat.uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert not ChatRun.objects.exists()
