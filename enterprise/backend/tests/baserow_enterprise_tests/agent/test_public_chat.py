import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from django.http import StreamingHttpResponse
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync
from rest_framework.response import Response
from rest_framework.test import APIClient

from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.core.chat_runs.models import ChatRun
from baserow_enterprise.agent.models import PublicChatAgentChannel
from baserow_enterprise.agent.public_chat_tokens import (
    encode_access_token,
    encode_conversation_token,
)
from baserow_enterprise.api.agent_public_chat.views import to_visitor_record
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.models import License
from tests.baserow.contrib.agent.conftest import configured_agent  # noqa: F401
from tests.baserow.contrib.agent.utils import hold_a_workspace_run

MESSAGE_FIELDS = ["content", "created_on", "id", "role", "status"]


def url(slug: str, view: str) -> str:
    return reverse(f"api:enterprise:agent_public_chat:{view}", kwargs={"slug": slug})


def bearer(token: str) -> dict[str, str]:
    return {"HTTP_BASEROW_AGENT_CHAT_AUTHORIZATION": f"JWT {token}"}


def start(
    api_client: APIClient,
    chat: PublicChatAgentChannel,
    content: str = "Hi",
    key: str | None = None,
    **headers,
) -> Response:
    return api_client.post(
        url(chat.slug, "conversations"),
        {"key": key or str(uuid4()), "content": content},
        format="json",
        **headers,
    )


def read(api_client: APIClient, chat: PublicChatAgentChannel, token: str) -> Response:
    return api_client.get(url(chat.slug, "conversation"), **bearer(token))


def send(
    api_client: APIClient,
    chat: PublicChatAgentChannel,
    token: str,
    content: str = "More",
    uuid: UUID | None = None,
) -> Response:
    return api_client.post(
        url(chat.slug, "messages"),
        {"uuid": str(uuid or uuid4()), "content": content},
        format="json",
        **bearer(token),
    )


def stream(
    api_client: APIClient, chat: PublicChatAgentChannel, run_id: str, **headers
) -> StreamingHttpResponse | Response:
    return api_client.get(
        reverse(
            "api:enterprise:agent_public_chat_stream:stream", kwargs={"slug": chat.slug}
        ),
        {"run_id": run_id},
        **headers,
    )


async def collect(response: StreamingHttpResponse) -> list[dict[str, Any]]:
    return [json.loads(chunk) async for chunk in response.streaming_content]


@pytest.fixture
def create_chat(
    configured_agent,  # noqa: F811
    enable_enterprise,
) -> Callable[..., PublicChatAgentChannel]:
    def create(
        agent: AgentApplication | None = None, password: str = "", **kwargs
    ) -> PublicChatAgentChannel:
        return PublicChatAgentChannel.objects.create(
            agent=agent or configured_agent(),
            password=PublicChatAgentChannel.hash_password(password),
            **kwargs,
        )

    return create


@pytest.fixture
def chat(create_chat) -> PublicChatAgentChannel:
    return create_chat(welcome_text="Ask me anything")


@pytest.mark.django_db
def test_info_names_the_chat_and_hides_a_protected_one_without_a_token(
    api_client, chat, create_chat
):
    protected = create_chat(password="secret", title="Support", welcome_text="Hello")

    assert api_client.get(url(chat.slug, "info")).json() == {
        "title": chat.agent.name,
        "welcome_text": "Ask me anything",
        "password_protected": False,
    }
    assert api_client.get(url(protected.slug, "info")).json() == {
        "title": "",
        "welcome_text": "",
        "password_protected": True,
    }
    assert api_client.get(
        url(protected.slug, "info"), **bearer(encode_access_token(protected))
    ).json() == {
        "title": "Support",
        "welcome_text": "Hello",
        "password_protected": True,
    }


UNUSABLE = {
    "unknown link": lambda chat: chat.delete(),
    "switched off": lambda chat: PublicChatAgentChannel.objects.filter(
        id=chat.id
    ).update(enabled=False),
    "trashed": lambda chat: PublicChatAgentChannel.objects.filter(id=chat.id).update(
        trashed=True
    ),
    "trashed agent": lambda chat: AgentApplication.objects.filter(
        id=chat.agent_id
    ).update(trashed=True),
    "workspace without Advanced or Enterprise": lambda chat: (
        License.objects.all().delete(),
        invalidate_cached_instance_wide_licenses(),
    ),
}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_unusable", list(UNUSABLE.values()), ids=list(UNUSABLE.keys())
)
def test_a_chat_that_cant_be_used_is_not_found(api_client, chat, make_unusable):
    slug = chat.slug
    make_unusable(chat)

    response = api_client.get(url(slug, "info"))

    assert (response.status_code, response.json()["error"]) == (
        404,
        "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,view,body",
    [
        ("get", "info", None),
        ("post", "auth", {"password": "secret"}),
        (
            "post",
            "conversations",
            {"key": str(uuid4()), "content": "Hi"},
        ),
        ("get", "conversation", None),
        ("post", "messages", {"uuid": str(uuid4()), "content": "Hi"}),
        ("post", "stop", None),
    ],
)
def test_every_endpoint_of_a_switched_off_chat_is_not_found(
    api_client, data_fixture, chat, method, view, body
):
    conversation = data_fixture.create_channel_conversation(channel=chat)
    token = encode_conversation_token(chat, conversation)
    PublicChatAgentChannel.objects.filter(id=chat.id).update(enabled=False)

    response = getattr(api_client, method)(
        url(chat.slug, view), body, format="json", **bearer(token)
    )

    assert (response.status_code, response.json()["error"]) == (
        404,
        "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
    )


@pytest.mark.django_db
def test_an_open_chat_starts_a_conversation_without_a_token(api_client, chat):
    response = start(api_client, chat)

    run = ChatRun.objects.get(chat_id=AgentConversation.objects.get(channel=chat).id)
    started = response.json()
    assert response.status_code == 200
    assert [
        (message["role"], message["content"], message["status"])
        for message in started["messages"]
    ] == [("visitor", "Hi", None), ("assistant", "", "running")]
    assert started["run_id"] == str(run.id)
    assert read(api_client, chat, started["token"]).json() == {
        "messages": started["messages"],
        "run_id": str(run.id),
    }


@pytest.mark.django_db
def test_a_repeated_first_message_returns_its_conversation_and_starts_nothing(
    api_client, chat
):
    key = str(uuid4())
    first = start(api_client, chat, key=key).json()

    repeated = start(api_client, chat, key=key).json()

    conversation = AgentConversation.objects.get(channel=chat)
    assert (repeated["messages"], repeated["run_id"]) == (
        first["messages"],
        first["run_id"],
    )
    assert (
        read(api_client, chat, repeated["token"]).json()["messages"]
        == (first["messages"])
    )
    assert ChatRun.objects.filter(chat_id=conversation.id).count() == 1


@pytest.mark.django_db
def test_the_uuid_members_read_never_recovers_a_visitor_conversation(api_client, chat):
    first = start(api_client, chat).json()
    conversation = AgentConversation.objects.get(channel=chat)

    taken = start(api_client, chat, key=str(conversation.uuid)).json()

    assert taken["token"] != first["token"]
    assert AgentConversation.objects.filter(channel=chat).count() == 2


@pytest.mark.django_db
def test_a_repeated_message_returns_it_and_starts_nothing(
    api_client, data_fixture, chat
):
    conversation = data_fixture.create_channel_conversation(channel=chat)
    token = encode_conversation_token(chat, conversation)
    uuid = uuid4()
    first = send(api_client, chat, token, uuid=uuid).json()

    repeated = send(api_client, chat, token, uuid=uuid)

    assert (repeated.status_code, repeated.json()) == (200, first)
    assert ChatRun.objects.filter(chat_id=conversation.id).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["conversations", "messages"])
def test_a_uuid_sent_again_with_other_content_conflicts(
    api_client, data_fixture, chat, view
):
    uuid = uuid4()
    if view == "conversations":
        start(api_client, chat, key=str(uuid))
        response = start(api_client, chat, "Other", key=str(uuid))
    else:
        conversation = data_fixture.create_channel_conversation(channel=chat)
        token = encode_conversation_token(chat, conversation)
        send(api_client, chat, token, uuid=uuid)
        response = send(api_client, chat, token, "Other", uuid=uuid)

    assert (response.status_code, response.json()["error"]) == (
        409,
        "ERROR_AGENT_MESSAGE_CONFLICT",
    )


@pytest.mark.django_db
def test_a_protected_chat_needs_the_token_from_auth(api_client, create_chat):
    chat = create_chat(password="secret")

    wrong = api_client.post(url(chat.slug, "auth"), {"password": "nope"}, format="json")
    token = api_client.post(
        url(chat.slug, "auth"), {"password": "secret"}, format="json"
    ).json()["access_token"]

    assert start(api_client, chat).status_code == 401
    assert wrong.status_code == 401
    assert start(api_client, chat, **bearer(token)).status_code == 200


@pytest.mark.django_db
def test_a_conversation_token_opens_only_its_own_conversation(
    api_client, data_fixture, chat, create_chat
):
    other_chat = create_chat()
    token = start(api_client, chat).json()["token"]
    forged = [
        encode_conversation_token(chat, conversation)
        for conversation in (
            data_fixture.create_channel_conversation(channel=other_chat),
            data_fixture.create_agent_conversation(agent=chat.agent, shared=True),
        )
    ]

    assert read(api_client, other_chat, token).status_code == 401
    assert send(api_client, other_chat, token).status_code == 401
    assert read(api_client, chat, encode_access_token(chat)).status_code == 401
    for forged_token in forged:
        assert read(api_client, chat, forged_token).status_code == 404
        assert send(api_client, chat, forged_token).status_code == 404


@pytest.mark.django_db
def test_a_changed_password_ends_every_token(api_client, create_chat):
    chat = create_chat(password="secret")
    access_token = encode_access_token(chat)
    conversation_token = start(api_client, chat, **bearer(access_token)).json()["token"]

    chat.password = PublicChatAgentChannel.hash_password("changed")
    chat.save()

    assert start(api_client, chat, **bearer(access_token)).status_code == 401
    assert read(api_client, chat, conversation_token).status_code == 401


@pytest.mark.django_db
def test_a_conversation_shows_only_the_text_of_the_visitor_and_the_agent(
    api_client, data_fixture, chat
):
    conversation = data_fixture.create_channel_conversation(channel=chat)
    for role in ("user", "trigger", "visitor"):
        message = data_fixture.create_agent_message(
            conversation=conversation, role=role, content=role
        )
    reply = data_fixture.create_agent_message(
        conversation=conversation,
        role="assistant",
        status="waiting",
        error_code="secret_code",
        steps=[{"id": "step", "kind": "tool_call", "tool_name": "create_rows"}],
    )
    data_fixture.create_agent_tool_approval(reply=reply, step_id="step")

    shown = read(api_client, chat, encode_conversation_token(chat, conversation))

    messages = shown.json()["messages"]
    assert [(item["id"], item["role"]) for item in messages] == [
        (str(message.uuid), "visitor"),
        (str(reply.uuid), "assistant"),
    ]
    assert [sorted(item) for item in messages] == [MESSAGE_FIELDS, MESSAGE_FIELDS]


def a_running_reply(api_client, data_fixture, chat) -> str:
    return start(api_client, chat).json()["token"]


def a_waiting_reply(api_client, data_fixture, chat) -> str:
    conversation = data_fixture.create_channel_conversation(channel=chat)
    data_fixture.create_agent_tool_approval(conversation=conversation)
    return encode_conversation_token(chat, conversation)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_reply,error",
    [
        (a_running_reply, "ERROR_CHAT_RUN_IN_PROGRESS"),
        (a_waiting_reply, "ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL"),
    ],
    ids=["running", "waiting"],
)
def test_a_visitor_cant_send_while_a_reply_runs_or_waits(
    api_client, data_fixture, chat, make_reply, error
):
    token = make_reply(api_client, data_fixture, chat)

    response = send(api_client, chat, token)

    assert (response.status_code, response.json()["error"]) == (409, error)


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["info", "conversation", "stream"])
def test_a_visitor_response_is_never_cached(api_client, chat, view):
    started = start(api_client, chat).json()
    token = bearer(started["token"])
    api_client.post(url(chat.slug, "stop"), **token)

    if view == "stream":
        response = stream(api_client, chat, started["run_id"], **token)
    else:
        response = api_client.get(url(chat.slug, view), **token)

    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_stop_cancels_the_running_reply(api_client, chat):
    started = start(api_client, chat).json()

    response = api_client.post(url(chat.slug, "stop"), **bearer(started["token"]))

    assert response.json() == {"status": "cancelled"}
    assert ChatRun.objects.get(id=started["run_id"]).status == "cancelled"


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
@pytest.mark.parametrize(
    "refusal,content,expected",
    [
        ("blank", "  ", (400, "ERROR_REQUEST_BODY_VALIDATION")),
        ("not ready", "Hi", (400, "ERROR_AGENT_NOT_READY")),
        ("run limit", "Hi", (429, "ERROR_AGENT_BUSY")),
    ],
)
def test_a_refused_first_message_leaves_no_conversation(
    api_client, data_fixture, create_chat, refusal, content, expected
):
    agent = data_fixture.create_agent_application() if refusal == "not ready" else None
    chat = create_chat(agent=agent)
    if refusal == "run limit":
        hold_a_workspace_run(data_fixture, chat.agent)

    response = start(api_client, chat, content=content)

    assert (response.status_code, response.json()["error"]) == expected
    assert not AgentConversation.objects.filter(channel=chat).exists()


@pytest.mark.django_db
def test_the_stream_of_a_finished_run_ends_with_the_reply_as_the_conversation_shows_it(
    api_client, chat
):
    started = start(api_client, chat).json()
    api_client.post(url(chat.slug, "stop"), **bearer(started["token"]))

    response = stream(api_client, chat, started["run_id"], **bearer(started["token"]))

    reply = read(api_client, chat, started["token"]).json()["messages"][-1]
    assert [
        (record["kind"], record["data"]) for record in async_to_sync(collect)(response)
    ] == [("run.finished", {"status": "cancelled", "message": reply})]


def record(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "data": data, "cursor": "1-1", "replayed": False}


@pytest.mark.parametrize(
    "shown,expected",
    [
        (record("step", {"id": "call", "tool_name": "create_rows"}), None),
        (record("progress", {"label": "Thinking"}), None),
        (record("run.created", {}), None),
        (record("run.started", {}), None),
        (
            record("text.delta", {"segment": 1, "text": "Hm", "variant": "thought"}),
            None,
        ),
        (
            record("text.delta", {"segment": 2, "text": "Hi", "step_id": "call"}),
            record("text.delta", {"segment": 2, "text": "Hi"}),
        ),
        (record("run.heartbeat", {}), record("run.heartbeat", {})),
        (
            record("run.replay_unavailable", {"reason": "expired", "run": {"id": 1}}),
            record("run.replay_unavailable", {"reason": "expired"}),
        ),
    ],
)
def test_a_visitor_sees_only_the_text_of_a_run(shown, expected):
    assert to_visitor_record(shown) == expected


@pytest.mark.django_db
def test_the_stream_needs_a_usable_chat_and_the_token_of_the_runs_conversation(
    api_client, chat
):
    token = start(api_client, chat).json()["token"]
    other_run_id = start(api_client, chat).json()["run_id"]

    other = stream(api_client, chat, other_run_id, **bearer(token))
    anonymous = stream(api_client, chat, other_run_id)

    assert (other.status_code, other.json()["error"]) == (
        404,
        "ERROR_CHAT_RUN_DOES_NOT_EXIST",
    )
    assert anonymous.status_code == 401

    PublicChatAgentChannel.objects.filter(id=chat.id).update(enabled=False)
    switched_off = stream(api_client, chat, other_run_id, **bearer(token))

    assert switched_off.json()["error"] == "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST"
